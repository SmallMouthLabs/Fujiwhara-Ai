"""Loads seat personas from `config/personas/*.yaml` into `SeatConfig` instances.

This is milestone 4: config-driven personas for the two anchor seats plus the
conductor (CLAUDE.md). The engine (`engine/session.py`) never changes based on
where a `SeatConfig` came from, by design (see `engine/seats.py`); this module's
only job is turning a persona file into one, validating early and loudly, since a
persona file is exactly the kind of config a person hand-edits and can typo.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .engine.seats import SeatConfig
from .providers import KNOWN_PROVIDERS

_REQUIRED_FIELDS = ("seat_id", "provider", "model", "system_prompt")

#: The roles `load_persona_set` knows how to assemble into a session. Adding a
#: genuinely new role (see docs/DECISIONS.md O3, a third seat) is a code change
#: here, same tradeoff as KNOWN_PROVIDERS in providers/__init__.py: a fixed
#: vocabulary the loader validates against, not an open string.
_KNOWN_ROLES = ("skeptic", "generator", "conductor", "reframer")


class PersonaConfigError(ValueError):
    """A malformed persona file or a malformed persona directory: missing or
    unknown fields, a bad type, an unrecognized provider or role, or (in
    `load_persona_set`) a role that's missing or claimed by more than one seat."""


def load_persona(path: str | Path) -> SeatConfig:
    """Load one seat's persona spec from a YAML file."""
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        raise PersonaConfigError(f"{path}: invalid YAML: {e}") from e

    if not isinstance(data, dict):
        raise PersonaConfigError(
            f"{path}: expected a YAML mapping at the top level, got {type(data).__name__}"
        )

    missing = [f for f in _REQUIRED_FIELDS if not data.get(f)]
    if missing:
        raise PersonaConfigError(f"{path}: missing required field(s): {', '.join(missing)}")

    provider = data["provider"]
    if provider not in KNOWN_PROVIDERS:
        known = ", ".join(sorted(KNOWN_PROVIDERS))
        raise PersonaConfigError(f"{path}: unknown provider {provider!r}; known providers: {known}")

    role = data.get("role") or ""
    if role and role not in _KNOWN_ROLES:
        known = ", ".join(_KNOWN_ROLES)
        raise PersonaConfigError(f"{path}: unknown role {role!r}; known roles: {known}")

    moves = data.get("moves") or []
    if not isinstance(moves, list) or not all(isinstance(m, str) for m in moves):
        raise PersonaConfigError(f"{path}: 'moves' must be a list of strings")

    try:
        return SeatConfig(
            seat_id=str(data["seat_id"]),
            provider=provider,
            model=str(data["model"]),
            system_prompt=str(data["system_prompt"]),
            role=role,
            disposition=str(data.get("disposition") or ""),
            moves=tuple(moves),
            max_tokens=int(data.get("max_tokens", 1024)),
            temperature=(float(data["temperature"]) if data.get("temperature") is not None else None),
        )
    except (TypeError, ValueError) as e:
        raise PersonaConfigError(f"{path}: invalid field value: {e}") from e


def load_personas(directory: str | Path) -> dict[str, SeatConfig]:
    """Load every persona file (*.yaml, *.yml) in a directory, keyed by seat_id.

    Raises `PersonaConfigError` if two files declare the same seat_id: almost
    always a copy-paste mistake, and cheap to catch here rather than at runtime.
    """
    directory = Path(directory)
    seats: dict[str, SeatConfig] = {}
    for path in sorted(directory.glob("*.yaml")) + sorted(directory.glob("*.yml")):
        seat = load_persona(path)
        if seat.seat_id in seats:
            raise PersonaConfigError(
                f"{path}: duplicate seat_id {seat.seat_id!r}, already loaded from another file"
            )
        seats[seat.seat_id] = seat
    return seats


@dataclass(frozen=True)
class PersonaSet:
    """The exact shape `DebateSession` needs, assembled from persona files by role."""

    debater_skeptic: SeatConfig
    debater_generator: SeatConfig
    conductor: SeatConfig
    reframer: SeatConfig | None = None

    def as_session_kwargs(self) -> dict:
        """`DebateSession(seed=..., **persona_set.as_session_kwargs())`."""
        return {
            "debaters": (self.debater_skeptic, self.debater_generator),
            "conductor": self.conductor,
            "reframer": self.reframer,
        }


def load_persona_set(directory: str | Path) -> PersonaSet:
    """Load a directory of persona files and organize them by role.

    Requires exactly one seat with role "skeptic", one "generator", and one
    "conductor"; "reframer" is optional (zero or one). Anything else, a missing
    required role or two seats claiming the same one, fails loudly: that's a
    config mistake, not something to silently pick a winner for.
    """
    directory = Path(directory)
    seats = load_personas(directory)

    by_role: dict[str, list[SeatConfig]] = {}
    for seat in seats.values():
        by_role.setdefault(seat.role, []).append(seat)

    def one(role: str, *, required: bool) -> SeatConfig | None:
        candidates = by_role.get(role, [])
        if len(candidates) > 1:
            ids = ", ".join(s.seat_id for s in candidates)
            raise PersonaConfigError(f"{directory}: more than one seat declares role {role!r}: {ids}")
        if not candidates:
            if required:
                raise PersonaConfigError(f"{directory}: no seat declares role {role!r}")
            return None
        return candidates[0]

    return PersonaSet(
        debater_skeptic=one("skeptic", required=True),
        debater_generator=one("generator", required=True),
        conductor=one("conductor", required=True),
        reframer=one("reframer", required=False),
    )
