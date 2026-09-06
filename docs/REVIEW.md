# Adversarial code review, and how each finding was resolved

A full adversarial review of the codebase was run after milestone 6. This file
records what it found and what was done about each item, so the findings are not
lost to chat scrollback. Every fix is committed; the commit hashes are noted.

One calibration note carried over from the review: this is a single-process local
CLI, with no server, no network listener, no auth surface, no concurrency, and no
persistence. The classic "production load" failure classes (auth bypass, race
conditions, connection-pool exhaustion) have no surface to attach to here, so the
review did not manufacture findings to fill those categories, and neither does
this record.

## Critical

### C1. `parse_uptake` and friends stripped every asterisk from model content. Fixed.
Confirmed content-corruption bug. `parse_uptake`, `build_disagreement_map`,
`check_stalled`, and `parse_framings` each ran `text.replace("*", "")` on the whole
response before parsing, to tolerate a model bolding a label as `**LABEL:**`. The
strip hit the captured value too, so every asterisk in a debater's argument, the
disagreement map, or a stall reason was silently deleted: markdown emphasis,
`price * volume` math, footnote and glob markers. The map is the tool's core
user-facing artifact, so this corrupted the product's own output.

Resolution (commit 9ab45a6): bold tolerance now lives in one place,
`engine/_parsing.py`'s `label()`, which matches the optional bold decoration
around a label only and never touches the captured value. All four global strips
removed. Regression tests assert content asterisks survive across uptake,
conductor, and reframe. One narrow, documented residual edge: a value beginning
with a literal `*` immediately after the label colon with no space may lose it.

### C2. Principle 2 (different models per anchor seat) was enforced nowhere. Fixed.
`load_persona_set` validated roles but never checked that the two anchor debaters
run on different models. CLAUDE.md calls different models "the main defense against
mode collapse and shared blind spots" and non-negotiable, yet a personas directory
with both debaters on the same model loaded and ran looking fine while defeating
the tool's premise.

Resolution (commit 9ab45a6): `load_persona_set` now rejects a set whose two
debaters share `(provider, model)`, with a message pointing at principle 2.
Matched on `(provider, model)`, so the same bare model name on two different
providers is allowed, and the conductor may reuse a debater's model (only the two
debaters must differ). Tests cover the rejection and both allowances.

### C3. Default `gpt-5` generator seat sent the deprecated `max_tokens`. Fixed; live-API confirmation still pending.
The OpenAI adapter sent `max_tokens`, which GPT-5 and the o-series reasoning models
reject; they require `max_completion_tokens`. The generator seat defaults to gpt-5,
so every generator turn would have failed on the first live call, and the test
suite structurally cannot catch it (no keys, no spend). The review flagged this as
"needs verification, cannot confirm from here."

Resolution (commit 097f0a9): verified against OpenAI's API docs and developer
forum (Sept 2026) that reasoning models require `max_completion_tokens` and only
accept the default temperature. The adapter now sends `max_completion_tokens`; the
common `ProviderAdapter` signature keeps `max_tokens` as its internal name, only
the OpenAI wire mapping changed. temperature is still passed only when a persona
sets it, with a comment that reasoning models reject non-default values.

Open caveat: the fix is grounded in published docs and unit-tested at the
wire-parameter level, but has not been exercised against the live OpenAI API. The
first real run with keys is the true confirmation.

## Tech debt

### Q1. `ProviderError.retryable` was dead metadata. Fixed.
The flag was set by both adapters and asserted in tests but read by no production
code. The SDKs already retry transient failures with backoff, so a second retry
layer keyed on this flag would double-retry.

Resolution (commit 097f0a9): field removed from `ProviderError` and both adapters;
`base.py` documents that retries are the SDK's job. `status_code` is kept, being
genuinely useful for reporting and caller branching. Tests assert on `status_code`.

### Q2. Unguarded `response.choices[0]` in the OpenAI adapter. Fixed.
An empty `choices` list (e.g. every candidate blocked by a content filter) raised a
raw `IndexError` that escaped the adapter's error-translation layer.

Resolution (commit 097f0a9): guarded into a `ProviderError` like every other
failure mode, with a test.

### Q3. `DebateSession.run()` was single-use but neither enforced nor documented it. Fixed.
`run()` appends to state seeded in `__init__`, so a second call replayed opening
takes onto existing history and produced a corrupt transcript.

Resolution (commit 097f0a9): a `_ran` flag rejects a second `run()` with a clear
`RuntimeError`, with a test.

### Q4. An auto-stall verdict could end the debate after a single round. Fixed.
Round 1 is by definition the first cross-critique, so it always introduces new
material; ending on a "stalled" judgment there is premature.

Resolution (commit ee7098c): `DebateSession` gained `min_rounds` (default 2,
clamped to <= `max_rounds`). The floor gates only the automatic stall: an explicit
user "stop" is honored from round 1, "continue" still overrides, and the judgment
is still recorded every round. Tests cover the floor, the clamp, and the
user-stop-wins-early case.

### Q5. The plain-text protocol is injectable by the models themselves. Documented.
Predecessor text is embedded verbatim into the next critique prompt, and responses
are parsed for plain-text markers, so a debater could emit those markers or
quote-breaking text and confuse the parser or counterpart. This is a robustness
ceiling of the plain-text-over-structured-output decision, not a security hole; the
threat model is debate quality between cooperating configured models.

Resolution (commit ee7098c): named the tradeoff and its ceiling in a comment at
`_critique_prompt`. No behavior change; revisit with delimiter/escaping or
provider-native structured output if adversarial inputs ever enter.

### Q6. `--max-rounds` accepted 0 and negatives. Fixed.
`--max-rounds 0` still fired the final map call on an empty debate.

Resolution (commit ee7098c): the flag uses a positive-int argparse type, rejecting
non-positive values at parse time with a clean usage error.

## Not bottlenecks (recorded so they are not re-raised)

- `_find_turn` is a linear scan, but the transcript is a handful of turns; O(n) is
  irrelevant and a dict would be premature.
- No concurrency bugs, because there is no concurrency. The two debaters within a
  round are provably independent and could be dispatched in parallel to halve
  per-round latency; this is a latent opportunity, not a defect, and is not worth
  doing until latency is a felt problem.
- Unbounded per-seat context growth (each turn resends the full history) is the
  real cost curve, inherent to stateless chat APIs, and was already known.
