# Multi-Model Debate Tool

A local tool where two different AI models, Claude and ChatGPT, debate your idea, critique
each other, and hold their own perspectives. You are the audience and the judge. Instead of
handing you one synthesized answer, it preserves the disagreement so you can read the
competing reasoning and reach your own conclusion.

## Status

All six MVP milestones from `CLAUDE.md` are built: provider adapters, per-seat state,
the core debate loop, config-driven personas, the (currently empty) move/hook
interface, and this CLI. See `docs/` for the full design.

## How it works

You give it a seed idea. Each model forms its own take without seeing the other's, then they
are revealed and the models critique and build on each other under a strict "uptake" rule
(every turn must engage a specific prior point). A non-contributing conductor runs the phases
and, at the end, produces a map of where the models agreed, where they genuinely split, and
the question left for you to decide. It never forces a consensus.

## Prerequisites

- An Anthropic API key.
- An OpenAI API key.
- Python 3.11+.

## Setup

```bash
git clone <your-repo-url>
cd debate-tool
cp .env.example .env
# then open .env and paste in your two API keys

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Running it

```bash
debate-tool --seed "Should we build a smart fridge?"
```

(or `python -m debate_tool`, same thing). Run from the repo root, so the default
`config/` paths resolve. Without `--seed` it prompts for one. Other flags:

- `--auto`: never prompt between rounds; run the whole session automatically
  (still shows progress; just skips the continue/stop/interject prompt).
- `--max-rounds N`: hard cap on cross-critique rounds (default 8).
- `--config-dir PATH`: use a different `config/` directory (default `config`).
- `--save PATH`: write a clean Markdown transcript of the debate to `PATH`
  (seed, reframed problem, every turn with its uptake tag, the conductor's
  per-round read, and the disagreement map). Terminal output is unchanged.

Mid-debate, after each round, you can continue automatically, stop now, force
another round even if the conductor judged the debate stalled, or interject a note
that gets added to both debaters' context before the next round.

### Running from anywhere (optional launcher)

`bin/debate-tool` is a self-locating launcher: it finds the project root relative
to its own path, activates the venv, and runs from the project directory (so
`.env` and the default `config/` resolve) no matter where you call it from. Put it
on your PATH once and `debate-tool` works from any directory:

```bash
ln -s "$(pwd)/bin/debate-tool" ~/.local/bin/debate-tool   # if ~/.local/bin is on your PATH
```

It follows symlinks to locate the repo, so the symlink above is enough; no editing
needed. One caveat: since it runs from the project directory, a relative `--save`
path lands in the project, not your current folder. Pass an absolute path (e.g.
`--save ~/Desktop/debate.md`) to write elsewhere.

## Project layout

```
config/    persona specs, technique "moves", and the orchestration policy (all editable)
src/       the debate engine, provider adapters, and state store
docs/       DESIGN.md, RESEARCH.md, DECISIONS.md
```

## Design docs

- `docs/DESIGN.md` — the architecture: seats, conductor, protocol, the two-layer split, MVP scope.
- `docs/DECISIONS.md` — what has been decided and why, plus what is still open.
- `docs/RESEARCH.md` — the group-dynamics and creative-cognition evidence the design rests on.

## A note on why this is a standalone app

It cannot be built as a single Claude artifact, because that sandbox can only call one
provider. Running Claude and ChatGPT together requires a small app you run yourself with
both keys, which is why this is local.
