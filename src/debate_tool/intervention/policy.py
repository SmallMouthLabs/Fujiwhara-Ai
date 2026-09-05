"""Loads the intervention policy (`config/policy.yaml`'s `hooks:` mapping) and
resolves/fires hooks against it. Mirrors `persona_config.py`'s shape: a directory
of small config files in, a validated Python object out, failing loudly on a
config mistake rather than at some later, harder-to-trace point.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from .hooks import Hook, HookEvent
from .moves import Move, MoveContext


class PolicyConfigError(ValueError):
    """A malformed move file or policy file: bad YAML, wrong shape, an unknown
    hook name, or a hook mapped to a move that was never registered."""


def load_moves(directory: str | Path) -> dict[str, Move]:
    """Load every move file (*.yaml, *.yml) in a directory, keyed by name.

    Returns an empty dict for an empty (or nonexistent) directory: the move
    library is empty at launch by design (docs/DECISIONS.md D8), not an error.
    """
    directory = Path(directory)
    if not directory.exists():
        return {}

    moves: dict[str, Move] = {}
    for path in sorted(directory.glob("*.yaml")) + sorted(directory.glob("*.yml")):
        try:
            data = yaml.safe_load(path.read_text())
        except yaml.YAMLError as e:
            raise PolicyConfigError(f"{path}: invalid YAML: {e}") from e

        if not isinstance(data, dict):
            raise PolicyConfigError(
                f"{path}: expected a YAML mapping at the top level, got {type(data).__name__}"
            )

        missing = [f for f in ("name", "when_to_use", "template") if not data.get(f)]
        if missing:
            raise PolicyConfigError(f"{path}: missing required field(s): {', '.join(missing)}")

        name = str(data["name"])
        if name in moves:
            raise PolicyConfigError(f"{path}: duplicate move name {name!r}, already loaded from another file")

        moves[name] = Move(name=name, when_to_use=str(data["when_to_use"]), template=str(data["template"]))

    return moves


class InterventionPolicy:
    """A move registry plus the hook -> move-names mapping resolved against it.

    Construct via `load_policy`, not directly, so the mapping is always
    pre-validated against the registry it was built with (see load_policy).
    """

    def __init__(self, moves: dict[str, Move], mapping: dict[Hook, tuple[str, ...]]) -> None:
        self._moves = moves
        self._mapping = mapping

    def resolve(self, hook: Hook) -> list[Move]:
        """The moves bound to a hook, in mapping order. Empty if the hook has no
        moves mapped to it, which is the common case while the move library is
        still empty (docs/DECISIONS.md D8)."""
        return [self._moves[name] for name in self._mapping.get(hook, ())]

    def fire(self, hook: Hook, context: MoveContext, round_index: int) -> HookEvent:
        """Resolve and render every move bound to `hook`. Always returns a
        HookEvent, even with nothing bound, so the condition that caused the
        firing is itself observable (see HookEvent's docstring)."""
        moves = self.resolve(hook)
        return HookEvent(
            hook=hook,
            round_index=round_index,
            applied_moves=tuple(m.name for m in moves),
            rendered=tuple(m.render(context) for m in moves),
        )


def load_policy(path: str | Path, moves: dict[str, Move]) -> InterventionPolicy:
    """Load a policy YAML file's `hooks:` mapping against an already-loaded move
    registry (see `load_moves`), validating every hook name and every referenced
    move name eagerly, since both are exactly the kind of thing a hand-edited
    config file can typo.
    """
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as e:
        raise PolicyConfigError(f"{path}: invalid YAML: {e}") from e

    if not isinstance(data, dict):
        raise PolicyConfigError(
            f"{path}: expected a YAML mapping at the top level, got {type(data).__name__}"
        )

    raw_hooks = data.get("hooks") or {}
    if not isinstance(raw_hooks, dict):
        raise PolicyConfigError(f"{path}: 'hooks' must be a mapping of hook name to a list of move names")

    mapping: dict[Hook, tuple[str, ...]] = {}
    for hook_name, move_names in raw_hooks.items():
        try:
            hook = Hook(hook_name)
        except ValueError:
            known = ", ".join(h.value for h in Hook)
            raise PolicyConfigError(f"{path}: unknown hook {hook_name!r}; known hooks: {known}") from None

        move_names = move_names or []
        if not isinstance(move_names, list) or not all(isinstance(m, str) for m in move_names):
            raise PolicyConfigError(f"{path}: hook {hook_name!r} must map to a list of move names")

        unknown = [m for m in move_names if m not in moves]
        if unknown:
            raise PolicyConfigError(
                f"{path}: hook {hook_name!r} references unregistered move(s): {', '.join(unknown)}"
            )

        mapping[hook] = tuple(move_names)

    return InterventionPolicy(moves=moves, mapping=mapping)
