"""The Debate Engine: seats, turns, per-seat state, the uptake rule, and the
disagreement map. Technique-agnostic per CLAUDE.md principle 1: nothing in this
package knows about SCAMPER, far analogy, or any other Intervention Layer move.
"""

from __future__ import annotations

from .conductor import DisagreementMap, StallJudgment, build_disagreement_map, check_stalled
from .map import MapSkeleton, SkeletonEntry, build_skeleton
from .seats import SeatConfig
from .session import DebateResult, DebateSession
from .turns import Phase, Stance, Turn
from .uptake import ParsedUptake, parse_uptake

__all__ = [
    "DebateResult",
    "DebateSession",
    "DisagreementMap",
    "MapSkeleton",
    "ParsedUptake",
    "Phase",
    "SeatConfig",
    "SkeletonEntry",
    "StallJudgment",
    "Stance",
    "Turn",
    "build_disagreement_map",
    "build_skeleton",
    "check_stalled",
    "parse_uptake",
]
