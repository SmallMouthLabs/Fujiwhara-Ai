"""Named conductor events (docs/DESIGN.md section 6) that a policy config can map
to moves. The conductor fires these; it never decides what happens next itself
(docs/DECISIONS.md D7), it looks up the policy's mapping and, if any moves are
bound to what fired, renders them. See `engine/session.py` for where (and, for
`ON_USER_STALL`, why not yet) each of these actually gets fired.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Hook(Enum):
    ON_USER_STALL = "on_user_stall"
    ON_EARLY_NARROWING = "on_early_narrowing"
    ON_FALSE_CONSENSUS = "on_false_consensus"
    ON_PHASE_CHANGE = "on_phase_change"


@dataclass(frozen=True)
class HookEvent:
    """A record of one hook firing: what fired, when, and what (if anything)
    responded. `applied_moves`/`rendered` are empty whenever no policy is
    configured, the hook has no moves mapped to it, or (today) always, since no
    real moves ship yet (docs/DECISIONS.md D8) -- the event is still recorded so
    the condition itself is observable even with nothing registered to answer it.
    """

    hook: Hook
    round_index: int
    applied_moves: tuple[str, ...] = ()
    rendered: tuple[str, ...] = ()
