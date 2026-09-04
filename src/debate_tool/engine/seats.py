"""The shape a seat needs to actually run.

As of milestone 4, `SeatConfig` instances are produced from `config/personas/*.yaml`
by `debate_tool.persona_config`, not written as Python literals (except in tests,
where a literal is still the simplest way to script a scenario). Nothing in the loop
(session.py) changes based on where a `SeatConfig` came from; that's the whole point
of the seam milestone 3 built.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SeatConfig:
    seat_id: str
    provider: str  # "anthropic" | "openai" (or whatever providers.get_adapter knows)
    model: str  # exact model id; never defaulted in code, see docs/DECISIONS.md D11
    system_prompt: str
    role: str = ""  # free-form label ("skeptic", "generator", ...); descriptive, not read by the engine
    disposition: str = ""  # free-form, descriptive only, e.g. "Critical, reasoned"
    moves: tuple[str, ...] = ()  # move names this seat may use; empty until milestone 5 implements moves
    max_tokens: int = 1024
    temperature: float | None = None
