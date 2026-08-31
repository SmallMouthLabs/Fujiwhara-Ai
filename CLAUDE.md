# CLAUDE.md

This file orients Claude Code on the project. Read it first, then `docs/DESIGN.md`
for the full architecture, `docs/DECISIONS.md` for what has already been settled and
why, and `docs/RESEARCH.md` for the evidence the design rests on.

## Project

**Working name:** Multi-Model Debate Tool (rename welcome).

A local tool where two different AI models, Claude and ChatGPT, discuss a user's idea,
critique each other's reasoning, and hold their own perspectives. The user is the audience
and the judge. The product deliberately preserves disagreement instead of collapsing it
into one answer, so the user can read the competing arguments and draw their own conclusion.

This is a debate you observe and adjudicate, not a creativity assistant that centers the
user. Keep that framing. Creativity techniques borrowed from the research (SCAMPER, far
analogy, schema violation, and so on) live in an optional, pluggable layer, never in the core.

## Non-negotiable design principles

These came out of a long design process. Do not quietly violate them. If you think one is
wrong, raise it with Patrick rather than coding around it.

1. **Two layers, one interface.** The Debate Engine (seats, turns, per-seat state, the
   uptake rule, the disagreement map) is strictly separate from the Intervention Layer
   (creativity techniques and human-element behaviors). The engine is technique-agnostic.
   Techniques attach as config-driven "moves" and "hooks." Build the seams even before any
   modules exist.
2. **Different models per anchor seat.** Claude in one seat, ChatGPT in the other. Never two
   personas on one model. This is the main defense against mode collapse and shared blind spots.
3. **The uptake rule.** Every debate turn must explicitly take up a specific prior point and
   steelman it, extend it, or rebut it with a reason. This is the load-bearing constraint
   against parallel monologue and sycophancy. Enforce it in the prompt contract, and validate
   it if feasible.
4. **No forced synthesis.** The system never resolves the debate into one verdict. The terminal
   output is a disagreement map: what the models agreed on, where they genuinely split with the
   reasoning on each side, and the open question left for the user.
5. **Non-contributing conductor.** The orchestrator runs the room but never contributes content
   of its own, so it cannot anchor the debate. Its touch varies by phase: light during
   divergence, firm during critique.
6. **Config over code.** Personas, per-seat move sets, phase sequence, stop conditions, and the
   intervention policy live in config, so behavior can be tuned without touching the engine.

## Decisions already made

- Anchor models: Claude and ChatGPT.
- Deployment: local, run with Patrick's own API keys (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`).
- This cannot run as a self-contained Claude artifact, because that sandbox cannot call a
  second provider. It is a standalone local app.

See `docs/DECISIONS.md` for the full rationale on each.

## Still open (settle with Patrick before building far)

- Language and stack: Python or Node. Pick one early. Either works. Match Patrick's preference.
- Interface: start with a CLI or a minimal web UI. A CLI is the faster path to a working loop.

## Proposed structure (adjust as needed)

```
debate-tool/
  CLAUDE.md
  README.md
  .env.example
  .gitignore
  config/
    personas/     # seat persona specs: claude-skeptic, chatgpt-generator, conductor, reframer
    moves/        # technique move definitions (empty at launch)
    policy.*      # phase sequence, stop conditions, hook -> move mapping
  src/            # engine, provider adapters, state store (language TBD)
  docs/
    DESIGN.md
    RESEARCH.md
    DECISIONS.md
```

## Current status

Design is complete and captured in `docs/`. Language/interface are settled (Python, CLI first;
see `docs/DECISIONS.md` D9-D13). Milestones 1-2 are done: `src/debate_tool/providers/` and
`src/debate_tool/state.py`, both with tests. Nothing else is built yet.

## Suggested first milestones

1. ~~Provider adapters for Anthropic and OpenAI behind one common interface.~~ Done
   (`src/debate_tool/providers/`).
2. ~~A per-seat state store that keeps each model's conversation history genuinely
   separate.~~ Done (`src/debate_tool/state.py`).
3. The core loop: user seed, independent takes (hidden from each other), reveal, cross-critique
   rounds with the uptake rule enforced, then the disagreement map.
4. Config-driven personas for the two anchor seats plus the conductor.
5. The move and hook interface, stubbed, with no technique modules implemented yet.
6. A minimal interface (CLI first) that runs a full session end to end.

Defer until the core works: the technique modules (SCAMPER and friends), adaptive intervention
policies, visual idea-state tracking, and the measurement/logging harness. The interfaces for
these should exist from the start; the implementations come later.

## Working conventions

- Keep the engine free of any technique-specific logic.
- Preserve each seat's independent conversation history. Do not merge contexts.
- Anything that resembles a creativity-assistant feature goes behind the intervention layer and
  is optional, so the debate-you-watch does not silently become a user-centered creativity tool.
- Flag strategic risks and tradeoffs before large changes. Patrick prefers to hear them first.
- In prose and docs, do not use em dashes.
