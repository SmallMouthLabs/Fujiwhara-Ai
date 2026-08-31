"""Per-seat conversation state.

This exists because of a specific failure mode this project is designed against:
two debaters that can see each other's raw context and drift into shared framing
instead of holding independent positions. See CLAUDE.md -> Working conventions:
"Preserve each seat's independent conversation history. Do not merge contexts."

`SeatStore` is the one place seat histories live. It never returns or accepts more
than one seat's history in a single call, and every read is a copy, so nothing
downstream can accidentally mutate a seat's history by holding a reference to it.
Nothing here knows about turn order, uptake, or the disagreement map; that's the
engine's job (later milestones), built on top of what this module guarantees.
"""

from __future__ import annotations

from .providers.base import Message

SeatId = str


class UnknownSeatError(KeyError):
    """Raised when a seat_id hasn't been registered with the store."""


class SeatAlreadyRegisteredError(ValueError):
    """Raised by `register` on a duplicate seat_id.

    Seat ids come from config (personas, later milestones); a duplicate almost
    always means a config mistake, and registration is the point where that
    mistake is cheapest to catch.
    """


class SeatStore:
    def __init__(self) -> None:
        self._histories: dict[SeatId, list[Message]] = {}

    def register(self, seat_id: SeatId) -> None:
        """Create an empty history for a seat."""
        if seat_id in self._histories:
            raise SeatAlreadyRegisteredError(seat_id)
        self._histories[seat_id] = []

    def append(self, seat_id: SeatId, message: Message) -> None:
        """Add one message to a single seat's history."""
        self._require(seat_id).append(message)

    def history(self, seat_id: SeatId) -> list[Message]:
        """Return a copy of one seat's history, and only that seat's history.

        A copy, not the live list, so a caller can't mutate the store's internal
        state by holding on to what this returns (e.g. passing it straight to
        `ProviderAdapter.generate` and then appending to it).
        """
        return list(self._require(seat_id))

    def seats(self) -> list[SeatId]:
        """The seat ids registered so far, in registration order."""
        return list(self._histories)

    def _require(self, seat_id: SeatId) -> list[Message]:
        try:
            return self._histories[seat_id]
        except KeyError:
            raise UnknownSeatError(seat_id) from None
