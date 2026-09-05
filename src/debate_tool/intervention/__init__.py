"""The Intervention Layer: moves and hooks. Strictly separate from the Debate
Engine (CLAUDE.md principle 1) -- the engine fires named hooks (see hooks.py)
without knowing what, if anything, responds. No real moves ship yet
(docs/DECISIONS.md D8); this package is the seam they drop into as
`config/moves/*.yaml` files, without any engine change.
"""

from __future__ import annotations

from .hooks import Hook, HookEvent
from .moves import Move, MoveContext, MoveRenderError
from .policy import InterventionPolicy, PolicyConfigError, load_moves, load_policy

__all__ = [
    "Hook",
    "HookEvent",
    "InterventionPolicy",
    "Move",
    "MoveContext",
    "MoveRenderError",
    "PolicyConfigError",
    "load_moves",
    "load_policy",
]
