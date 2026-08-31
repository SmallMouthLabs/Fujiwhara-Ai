# config/

Everything tunable lives here, so behavior changes without touching the engine.

- `personas/` — one spec per seat: the two anchor debaters (Claude skeptic, ChatGPT generator),
  the conductor, and the optional reframer. A persona spec is the seat's role, disposition,
  system prompt, and the set of moves it is allowed to use.
- `moves/` — technique definitions for the intervention layer (SCAMPER, far analogy, schema
  violation, random connection, semantic-escape, and so on). Empty at launch. Each move is a
  prompt template plus a "when to use" note.
- `policy.*` — the orchestration policy: phase sequence, the oscillation rhythm, stop conditions,
  and the mapping from conductor hooks (for example `on_user_stall`) to moves.

Format (JSON, YAML, or other) is an implementation choice, not yet made; it'll be settled
alongside milestone 4 (config-driven personas) rather than milestone 1.
