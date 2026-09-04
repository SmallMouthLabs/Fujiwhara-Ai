# config/

Everything tunable lives here, so behavior changes without touching the engine.

- `personas/`: one YAML file per seat: the two anchor debaters (Claude skeptic, ChatGPT
  generator), the conductor, and the optional reframer. Loaded by
  `src/debate_tool/persona_config.py` into `SeatConfig` instances (`load_persona_set` returns
  the whole set, organized by role, in the shape `DebateSession` needs directly). Required
  fields: `seat_id`, `provider`, `model`, `system_prompt`. Optional: `role` (one of `skeptic`,
  `generator`, `conductor`, `reframer`; required for `load_persona_set` to place a seat),
  `disposition` (free text, descriptive only), `moves` (list of move names, empty until
  milestone 5 exists), `max_tokens`, `temperature`.
- `moves/` — technique definitions for the intervention layer (SCAMPER, far analogy, schema
  violation, random connection, semantic-escape, and so on). Empty at launch. Each move is a
  prompt template plus a "when to use" note.
- `policy.*` — the orchestration policy: phase sequence, the oscillation rhythm, stop conditions,
  and the mapping from conductor hooks (for example `on_user_stall`) to moves. Not built yet;
  today's phase/stop-condition logic (`engine/session.py`) is hardcoded pending milestone 5.

Format is YAML, chosen when personas landed (milestone 4): human-editable, comments for the
"why" behind a persona choice, and multi-line system prompts read cleanly with `|` block scalars.
