# Decisions

A running log of what has been settled, why, and what is still open. Update this as the project
evolves rather than letting decisions live only in someone's head.

---

## Decided

### D1. Product spine is a debate you adjudicate (option b)
The tool exists so distinct models argue and the user extracts their own conclusion from the
friction. The alternative (a user-centered co-creativity assistant) is explicitly not the spine,
though its techniques are borrowed as an optional layer.
**Why:** the user's original goal was to watch models critique each other and reach their own
truth, not to be handed an answer. The research also shows preserved productive disagreement has
value that consensus destroys.

### D2. Anchor models are Claude and ChatGPT
One seat each, on different providers.
**Why:** using two different underlying models is the main defense against mode collapse and shared
blind spots. Two personas on one model would converge. Claude defaults to the skeptic seat and
ChatGPT to the generator seat, matching their observed dispositions, but this is a config default,
not a law.

### D3. Runs locally with the user's own API keys
`ANTHROPIC_API_KEY` and `OPENAI_API_KEY` in a local `.env`.
**Why:** it cannot be a self-contained Claude artifact, because that sandbox can only call one
provider. Local is the simplest starting point. Deployment can come later.

### D4. Two-layer architecture: engine vs intervention layer
The debate engine is strictly separate from a pluggable, config-driven intervention layer where all
creativity techniques and human-element behaviors live.
**Why:** the user's vital requirement is being able to change and add human-element techniques later
without rewriting the core. Decoupling makes that cheap. Build the seams now even if the modules are
empty at launch.

### D5. The uptake rule is a core engine constraint
Every debate turn must explicitly take up a specific prior point and steelman, extend, or rebut it.
**Why:** across the discourse research, uptake is the clearest separator of strong from weak
discussion, and it is the direct defense against parallel-monologue mode collapse and sycophancy.

### D6. No forced synthesis; terminal output is a disagreement map
The system never produces one verdict. It ends on a map of agreements, live splits with reasoning on
each side, and the open question for the user.
**Why:** synthesis into one answer is the exact thing that makes multi-model setups pointless. The
map preserves the friction while still giving the user structure to think against.

### D7. The conductor contributes no content
A dedicated orchestrator runs phases, enforces uptake, balances the floor, and writes the map, but
never argues, so it cannot anchor. Its touch is light during divergence and firm during critique.
**Why:** evidence that a non-contributing facilitator raises reasoning, and that a leader who speaks
first anchors the room. The variable touch reflects that heavy guidance raises rigor but suppresses
generativity.

### D8. Creativity technique modules are deferred, but their interfaces are not
SCAMPER, far analogy, schema violation, random connection, semantic-escape cues, and similar become
`moves` in the intervention layer, fired by conductor `hooks`. Interfaces exist from day one;
implementations come after the core loop works.
**Why:** keeps the MVP small while guaranteeing the future integration the user cares about is a
config and module exercise, not a rewrite.

### D9. Language and stack: Python
**Why:** Patrick's call, no further rationale recorded. Settles O1.

### D10. Interface: CLI first
A minimal web UI may follow later, but the MVP is CLI only.
**Why:** reaches a working end-to-end loop fastest. Settles O2.

### D11. Default models: flagship, swappable via config
Claude Sonnet 5 for the skeptic seat, GPT-5 for the generator seat, as defaults only. Model IDs
live in seat config, not code, so any seat can be pointed at a different model without touching
the engine.
**Why:** flagship models give the debate the best shot at genuine critique. Patrick was explicit
that swapping models must stay easy, which the config-over-code principle (D4/6) already requires.

### D12. Disagreement map: hybrid generation
Every debate turn must carry structured tags: which prior point (if any) it takes up, and its
stance toward it (agree / extend / rebut). Code assembles the map's skeleton (the agreements
list, the split list, the open question slot) purely from those tags. A single constrained LLM
call then fills in prose inside that fixed skeleton, prompted to phrase only, never to introduce
a claim, agreement, or split that is not already present in the tags/transcript.
**Why:** pure code assembly is brittle if tagging is ever imperfect or a nuance does not reduce
to three stance labels; a free-form LLM summary risks the conductor quietly contributing content,
which D7 forbids. The hybrid keeps the LLM inside a cage that code defines.

### D13. Stop condition: auto-detect stalling, user can always override
After each cross-critique round, the conductor makes a lightweight LLM judgment call on whether
new arguments are still appearing versus the round restating prior points. If it judges the
debate has stalled, it surfaces that to the user and suggests ending, but the user can always
continue or end manually at any point regardless of that judgment.
**Why:** matches the design doc's stated stop condition ("ends when new arguments stop
appearing") more faithfully than a manual-only or fixed-round-cap MVP, while keeping the user as
final authority per D6.

---

## Open

### O3. A third seat and third model
Gemini or another model as an optional third seat is out of scope for the MVP but should not be
designed out. Seats are config, so adding one later should be straightforward.

---

## Superseded or rejected

- **Forking an existing repo (quorum, ai-debate, and others).** Explored and set aside for now. The
  candidates were mostly zero-star, unproven, and oriented toward forced consensus, which is the one
  thing this project rejects. The requirement here (preserve disagreement, user drives turn-taking) is
  a small enough orchestration surface that a clean build is likely less work than surgically
  de-synthesizing someone else's untested code. Revisit only if a specific repo proves genuinely
  reusable.
