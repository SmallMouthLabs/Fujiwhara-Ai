"""The minimal, code-level shape a seat needs to actually run.

`SeatConfig` is deliberately not loaded from a config file yet: that's milestone 4
(config-driven personas). The loop below only depends on this shape, so milestone 4
just has to produce `SeatConfig` instances from YAML/JSON instead of Python literals;
nothing in the loop itself changes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SeatConfig:
    seat_id: str
    provider: str  # "anthropic" | "openai" (or whatever providers.get_adapter knows)
    model: str  # exact model id; never defaulted in code, see docs/DECISIONS.md D11
    system_prompt: str
    max_tokens: int = 1024
    temperature: float | None = None
