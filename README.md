# Multi-Model Debate Tool

A local tool where two different AI models, Claude and ChatGPT, debate your idea, critique
each other, and hold their own perspectives. You are the audience and the judge. Instead of
handing you one synthesized answer, it preserves the disagreement so you can read the
competing reasoning and reach your own conclusion.

## Status

Design phase complete. Implementation not started. See `docs/` for the full design.

## How it works (intended)

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

A run command for the CLI will be added once the core debate loop is built (see
`CLAUDE.md` -> Suggested first milestones). Right now the codebase has the provider
adapters (`src/debate_tool/providers/`) for talking to Claude and ChatGPT behind one
common interface, with tests, and not much else yet.

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
