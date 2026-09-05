# config/

Everything tunable lives here, so behavior changes without touching the engine.

- `personas/`: one YAML file per seat: the two anchor debaters (Claude skeptic, ChatGPT
  generator), the conductor, and the optional reframer. Loaded by
  `src/debate_tool/persona_config.py` into `SeatConfig` instances (`load_persona_set` returns
  the whole set, organized by role, in the shape `DebateSession` needs directly). Required
  fields: `seat_id`, `provider`, `model`, `system_prompt`. Optional: `role` (one of `skeptic`,
  `generator`, `conductor`, `reframer`; required for `load_persona_set` to place a seat),
  `disposition` (free text, descriptive only), `moves` (list of move names this seat may use;
  wiring which seat gets which move isn't built yet, see below), `max_tokens`, `temperature`.
- `moves/`: technique definitions for the intervention layer (SCAMPER, far analogy, schema
  violation, random connection, semantic-escape, and so on). Empty at launch, by design
  (docs/DECISIONS.md D8): each move is just a `name`, `when_to_use` note, and a `template`
  string, loaded by `src/debate_tool/intervention/policy.py`'s `load_moves` into `Move`
  instances. No Python subclassing needed to add one; it's config, like a persona.
- `policy.yaml`: the hook -> move-names mapping only, loaded by `load_policy` into an
  `InterventionPolicy` that `DebateSession` fires hooks against (`on_user_stall`,
  `on_early_narrowing`, `on_false_consensus`, `on_phase_change`; see
  `src/debate_tool/intervention/hooks.py`). Ships with every hook listed and nothing mapped,
  since the move library above is empty. **Not** yet covered here, despite the name: phase
  sequence, the oscillation rhythm, and stop conditions, which config/README.md once described
  as part of this file too. Those are still hardcoded in `engine/session.py`; folding them into
  config is a bigger change than milestone 5 (the move/hook interface) scoped, and hasn't been
  decided.

Format is YAML, chosen when personas landed (milestone 4): human-editable, comments for the
"why" behind a persona or move choice, and multi-line system prompts and templates read cleanly
with `|` block scalars.
