"""The uptake rule's prompt contract and parser.

Enforced two ways, per docs/DECISIONS.md D5 ("in the prompt contract, and validate it
if feasible"): every cross-critique prompt requires this exact three-field format, and
`session.py` sends a response back once with a corrective nudge on a parse failure
before accepting whatever comes back, flagged as `uptake_ok=False` if it still doesn't
conform. This is deliberately plain-text and regex-parsed rather than a provider
structured-output feature (Anthropic's `output_config.format`, OpenAI's JSON mode):
those two features don't line up closely enough to keep `ProviderAdapter` symmetric
across providers without leaking provider-specific config through the common
interface (see providers/base.py).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ._parsing import label
from .turns import Stance

UPTAKE_FORMAT_INSTRUCTIONS = """
Respond in exactly this three-field format, nothing before the first field and nothing after the last:

TARGET: the specific prior point you are taking up, quoted or closely paraphrased
STANCE: one of: steelman, extend, rebut
ARGUMENT: your argument, giving your reason
""".strip()

CORRECTIVE_NUDGE = (
    "That response didn't follow the required format. "
    "Redo it in exactly this three-field format, nothing before or after it:\n\n" + UPTAKE_FORMAT_INSTRUCTIONS
)

# Bold-label tolerance lives in `label()` (see _parsing.py), applied only around
# the labels, never to the captured value.
#
# The capture group is `.*?` (zero-or-more), not `.+?`: `.+?` must consume at least
# one character before it's allowed to check the lookahead, so on an empty/blank
# field it eats the lookahead's own leading "\n" and then can never find it again,
# swallowing the next field's label text into this group. `.*?` can match zero
# characters, so it can satisfy the lookahead without consuming past the boundary.
_TARGET_RE = re.compile(label("TARGET") + r"(.*?)(?=\n\s*" + label("STANCE") + r"|\Z)", re.IGNORECASE | re.DOTALL)
_STANCE_RE = re.compile(label("STANCE") + r"(steelman|extend|rebut)\b", re.IGNORECASE)
_ARGUMENT_RE = re.compile(label("ARGUMENT") + r"(.+)\Z", re.IGNORECASE | re.DOTALL)


@dataclass(frozen=True)
class ParsedUptake:
    ok: bool
    target: str | None
    stance: Stance | None
    argument: str | None


def parse_uptake(raw_text: str) -> ParsedUptake:
    """Extract TARGET/STANCE/ARGUMENT from a raw response.

    Tolerant of light markdown (bold labels) and of stray whitespace, since that's
    the kind of drift a retry is meant to absorb, not reject outright. Bold tolerance
    is confined to the labels (see `label()` in _parsing.py); asterisks inside the
    captured argument, target, etc. are preserved verbatim. `ok` is True only when
    all three fields were found and non-empty.
    """
    target_m = _TARGET_RE.search(raw_text)
    stance_m = _STANCE_RE.search(raw_text)
    argument_m = _ARGUMENT_RE.search(raw_text)

    target = target_m.group(1).strip() if target_m else None
    stance = Stance(stance_m.group(1).lower()) if stance_m else None
    argument = argument_m.group(1).strip() if argument_m else None

    ok = bool(target) and stance is not None and bool(argument)
    return ParsedUptake(ok=ok, target=target, stance=stance, argument=argument)
