# Design

The canonical architecture for the tool. Read `CLAUDE.md` first for the short version and
the non-negotiable principles.

---

## 1. What this is, and what it is not

- **Spine:** a debate you observe and adjudicate. Distinct models argue, take each other up,
  and hold their own perspective. There is no forced consensus and no final verdict from the
  system.
- **Not this:** a co-creativity tool built to scaffold the user's own thinking with the user at
  the center. That framing dominates the research literature, and its techniques are worth
  borrowing, but as an optional layer, not the foundation.
- **Terminal output:** a map of the disagreement (what the models converged on, where they
  genuinely split and the reasoning on each side, and the open question left for the user),
  never a resolved answer.

---

## 2. Core architecture: two layers, one interface

The single most important decision. Keep these strictly separated.

- **Debate Engine.** Orchestrates seats, turn order, the uptake rule, per-seat conversation
  state, and the disagreement map. Model-agnostic and technique-agnostic. It knows nothing
  about SCAMPER or psychological framing.
- **Intervention Layer.** A library of "moves" and "hooks" that seats or the conductor can
  invoke. This is where every human-element and creativity technique lives, now and later.
  Entirely config-driven.
- **The interface between them.** Seats declare which moves they are allowed to use. The
  conductor exposes named hook points (events) that map to interventions through a policy
  config. Adding or tuning a technique means editing config, not rewriting the engine.

This is what makes the "tweak how the agents deal with the human element" requirement cheap to
satisfy later: build the seams now, even if the modules come later.

---

## 3. The seats

| Seat | Function | Disposition | Notes |
|---|---|---|---|
| Reframer (optional, runs first) | Problem construction | Curious, abductive | Offers alternate framings of the actual problem before ideation. Reframing is where a lot of the creativity lives. |
| Generator / Explorer | Expands, pushes into new territory | Generative, optimistic | The "campaigner." Widens the space. Default model: ChatGPT. |
| Skeptic / Evaluator | Subtracts, stress-tests | Critical, reasoned | The natural skeptic seat. Default model: Claude. |
| Conductor | Runs the room | Impartial, non-contributing | See section 4. |

Rule: the two anchor debaters are different underlying models (Claude and ChatGPT), not two
personas on one model. This is the main defense against mode collapse and shared blind spots.
Seats are config, so more can be added later.

The Claude-as-skeptic, ChatGPT-as-generator split is the default because it matches the
observed dispositions that started this whole project. It is a default, not a law, and can be
swapped in config.

---

## 4. The conductor

- Never contributes content of its own, so it cannot anchor the debate.
- Variable touch: light during divergence to protect generativity, firm during critique to
  enforce rigor. Evidence shows a heavy hand raises reasoning but kills exploration, so the
  touch has to change by phase.
- Enforces the uptake rule, balances floor time, manages phase transitions, and produces the
  disagreement map.
- Does not adjudicate. That is the user's job.

---

## 5. The protocol

Default loop, oscillatory rather than one-shot:

1. User seed.
2. (Optional) Reframer pass. Offers alternate problem framings; the user picks or edits one.
3. Independent takes. Each debater answers privately, without seeing the other, to prevent
   anchoring on whoever spoke first.
4. Reveal.
5. Cross-critique rounds with mandatory uptake.
6. Oscillation. The conductor alternates "expand" phases and "stress-test" phases rather than
   mixing both at once.
7. The user may interject at any point.
8. Terminal: the disagreement map. The user decides.

**Stop condition:** the debate ends when the user calls it, or when new arguments stop
appearing. It never ends because the models agreed. Agreement is never the reward.

**The uptake rule (load-bearing).** Every turn must explicitly take up a specific prior point
and do something to it: steelman it, extend it, or rebut it with a reason. This one constraint
is the strongest single defense against both parallel-monologue mode collapse and sycophantic
nodding, and it is exactly what the weakest human groups in the research lacked.

---

## 6. The extensibility layer (the vital part)

Two primitives, both config-driven.

**Moves.** Discrete techniques attachable to a seat or callable by the conductor. Each move is
a prompt template plus a "when to use" note. Example library to grow into:

| Move | Effect | Typical trigger |
|---|---|---|
| Far analogy (3 prompts) | Higher novelty, broader search | Ideas feel obvious |
| Random connection | Fluency and flexibility | Stuck in one region |
| Schema violation | Flexibility, breaks assumptions | Everything sounds conventional |
| SCAMPER | Originality | Systematic variation of a seed |
| Semantic escape cue | Breaks local fixation | User stalls |
| Stakeholder reframe | More useful, elaborated ideas | Early framing |
| Deepen vs diversify | Trust and adoption | After a seed idea appears |

The three analogy prompts, for reference: "what else works like this," "what solves a
structurally similar problem in another domain," and "what opposite system succeeds by
violating this assumption."

**Hooks.** Named conductor events that can fire an intervention through a policy config:

- `on_user_stall`
- `on_early_narrowing` (idea space being reused)
- `on_false_consensus` (disagreement collapsing into agreement without real engagement)
- `on_phase_change`

Everything tunable lives in config: personas, per-seat move sets, phase sequence, stop rules,
and the intervention policy that maps hooks to moves. At launch the implemented move set can be
empty. The point is that the hook points and the move interface exist, so future techniques drop
in without engine changes.

---

## 7. MVP scope vs later

**Build now (MVP):**
- Two debaters on different models (Claude and ChatGPT), plus the conductor, plus an optional
  reframer.
- The oscillatory protocol with independent takes first.
- Uptake enforcement.
- Disagreement-map output.
- User interjection at any turn.
- Config-driven personas.
- The move and hook interface, even if no moves are implemented yet.
- Runs as a local app with the user's own Anthropic and OpenAI keys.

**Later (interfaces stubbed now):**
- The technique move-modules from section 6.
- Adaptive intervention policies keyed off the hooks.
- Visual idea-state tracking (branch inspection, reuse detection).
- A measurement and logging harness: idea variety, originality, elaboration, fixation,
  adoption, and whether the user expands, rejects, or merely copies each output.

---

## 8. Open risks to track

- **Role-occupancy fidelity.** Whether the skeptic keeps subtracting when the generator's output
  is right in front of it. Test this early. Mitigations: different models, the explicit uptake
  rule, conductor re-anchoring.
- **Mode collapse and shared blind spots.** Mitigate with different providers and, later,
  technique injection.
- **Over-dominance (the Goldilocks effect).** Too directive a system backfires. The variable-touch
  conductor and keeping the user in control are the guards.
- **Option (a) creep.** Keep the human-element layer optional, so the debate the user watches does
  not quietly turn into a user-centered creativity tool unless they deliberately switch that on.

---

## 9. Tech shape

- Thin orchestrator in Python or Node (decision pending, see `DECISIONS.md`).
- Provider adapters (Anthropic, OpenAI, and later optionally Gemini) behind a common interface.
- A state store that keeps each seat's conversation history genuinely separate.
- Config files for personas, moves, and intervention policy.
- Interface: CLI first, then optionally a minimal web front end.

Settled inputs: the two anchor seats are Claude and ChatGPT, and the tool runs locally with the
user's own keys.
