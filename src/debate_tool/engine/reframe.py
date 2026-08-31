"""The optional reframer pass's prompt contract and parser.

Per docs/DESIGN.md section 3, the reframer offers alternate framings of the actual
problem and "the user picks or edits one", a real interaction, not something the
engine can resolve on its own. `run_reframe` in session.py takes a `choose_framing`
callback for exactly that reason: this milestone builds the mechanism (ask for
framings, parse them, let something choose), and the real terminal prompt that lets
a person choose is milestone 6's job (the CLI). The default callback just takes the
first framing, so the session still runs end to end without a caller supplying one.
"""

from __future__ import annotations

import re

REFRAME_PROMPT = """
The user's seed idea:

{seed}

Offer 2-3 alternate framings of the actual problem behind this idea, before any
ideation happens. Each framing should be a genuinely different way of understanding
what problem is really being solved, not a rephrasing of the same one. Respond in
exactly this format, one framing per block, nothing before or after:

FRAMING: first alternate framing
FRAMING: second alternate framing
FRAMING: third alternate framing (optional)
""".strip()

# `.*?`, not `.+?` -- see the comment on uptake.py's _TARGET_RE for why: `.+?` would
# swallow a blank framing block's boundary and eat the next "FRAMING:" label as content.
_FRAMING_RE = re.compile(r"FRAMING:[ \t]*(.*?)(?=\n\s*FRAMING:|\Z)", re.IGNORECASE | re.DOTALL)


def parse_framings(raw_text: str) -> list[str]:
    text = raw_text.replace("*", "")  # tolerate "**FRAMING:**"-style bold labels
    return [m.strip() for m in _FRAMING_RE.findall(text) if m.strip()]
