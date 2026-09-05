"""The Move interface: discrete techniques from the intervention layer's library.

Per docs/DESIGN.md section 6, "each move is a prompt template plus a 'when to use'
note." That means a move needs no Python at all: `Move` is a plain data shape, and
a future technique (SCAMPER, far analogy, schema violation, ...) is added as a new
`config/moves/*.yaml` file, the same way a persona is a `config/personas/*.yaml`
file. No real moves exist yet (docs/DECISIONS.md D8); this module and
`move_config.py` are the seam they drop into without any engine change.
"""

from __future__ import annotations

from dataclasses import dataclass


class MoveRenderError(ValueError):
    """Raised when a move's template references a placeholder MoveContext doesn't
    provide. A template authored against the wrong context shape should fail
    loudly at render time, not silently emit `{recent_targets}` as literal text."""


@dataclass(frozen=True)
class MoveContext:
    """What a move's template is rendered against. Deliberately minimal and
    read-only: a move shapes a prompt injection from what the engine gives it
    here, it doesn't reach into engine state directly. Extend with more fields as
    real moves need them; nothing here is proven against an actual move yet."""

    seed: str
    seat_id: str
    recent_targets: tuple[str, ...] = ()

    def as_format_kwargs(self) -> dict[str, str]:
        return {
            "seed": self.seed,
            "seat_id": self.seat_id,
            "recent_targets": ", ".join(self.recent_targets),
        }


@dataclass(frozen=True)
class Move:
    """One technique: a name, a note on when to reach for it, and a prompt
    template. `when_to_use` is documentation for whoever writes the policy config
    that wires a move to a hook; it doesn't affect `render`."""

    name: str
    when_to_use: str
    template: str

    def render(self, context: MoveContext) -> str:
        try:
            return self.template.format(**context.as_format_kwargs())
        except KeyError as e:
            raise MoveRenderError(
                f"move {self.name!r}: template references unknown placeholder {e}"
            ) from e
