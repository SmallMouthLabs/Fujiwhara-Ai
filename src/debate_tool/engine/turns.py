"""The uptake-tagged turn: the load-bearing unit of the cross-critique protocol.

See CLAUDE.md principle 3 and docs/DECISIONS.md D5: every cross-critique turn must
take up a specific prior point and steelman it, extend it, or rebut it with a reason.
The three stances also double as the tags docs/DECISIONS.md D12 needs to assemble the
disagreement map's skeleton in code, without a free-form LLM summary: STEELMAN and
EXTEND both read as convergence on that point, REBUT as a live split.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Stance(Enum):
    STEELMAN = "steelman"
    EXTEND = "extend"
    REBUT = "rebut"


class Phase(Enum):
    """Which mode the round is run in. See docs/DESIGN.md section 4: light touch
    during divergence to protect generativity, firm touch during critique to
    enforce rigor. The whole session oscillates between the two together, rather
    than each seat running its own phase independently."""

    EXPAND = "expand"
    STRESS_TEST = "stress_test"

    def next(self) -> "Phase":
        return Phase.STRESS_TEST if self is Phase.EXPAND else Phase.EXPAND


@dataclass(frozen=True)
class Turn:
    """One seat's contribution, opening or cross-critique.

    `target`/`stance` are None for the opening, independent-takes turn: the uptake
    rule only applies once there is a prior point to take up (post-reveal). `raw`
    keeps the full unparsed response for debugging even when `text` is just the
    parsed ARGUMENT field.
    """

    seat_id: str
    round_index: int  # 0 for the opening take, 1.. for cross-critique rounds
    phase: Phase | None  # None for the opening take
    text: str
    target: str | None = None
    stance: Stance | None = None
    uptake_ok: bool = True
    raw: str = ""
