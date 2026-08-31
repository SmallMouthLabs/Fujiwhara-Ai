"""Tests for SeatStore, focused on the one thing it exists to guarantee:
genuine isolation between seats' conversation histories.
"""

from __future__ import annotations

import pytest

from debate_tool.providers.base import Message
from debate_tool.state import SeatAlreadyRegisteredError, SeatStore, UnknownSeatError


def test_register_creates_empty_history():
    store = SeatStore()
    store.register("skeptic")

    assert store.history("skeptic") == []
    assert store.seats() == ["skeptic"]


def test_register_duplicate_seat_raises():
    store = SeatStore()
    store.register("skeptic")

    with pytest.raises(SeatAlreadyRegisteredError):
        store.register("skeptic")


def test_append_and_history_roundtrip():
    store = SeatStore()
    store.register("skeptic")
    msg = Message(role="user", content="seed idea")

    store.append("skeptic", msg)

    assert store.history("skeptic") == [msg]


def test_seats_are_genuinely_isolated():
    """The load-bearing test: seat A's turns must never leak into seat B's history."""
    store = SeatStore()
    store.register("skeptic")
    store.register("generator")

    store.append("skeptic", Message(role="user", content="skeptic sees this"))
    store.append("generator", Message(role="user", content="generator sees this"))
    store.append("generator", Message(role="assistant", content="generator's own reply"))

    skeptic_history = store.history("skeptic")
    generator_history = store.history("generator")

    assert [m.content for m in skeptic_history] == ["skeptic sees this"]
    assert [m.content for m in generator_history] == [
        "generator sees this",
        "generator's own reply",
    ]
    # Neither seat's content appears in the other's history.
    assert "generator sees this" not in [m.content for m in skeptic_history]
    assert "skeptic sees this" not in [m.content for m in generator_history]


def test_history_returns_a_copy_not_the_live_list():
    store = SeatStore()
    store.register("skeptic")
    store.append("skeptic", Message(role="user", content="first"))

    returned = store.history("skeptic")
    returned.append(Message(role="assistant", content="smuggled in"))

    assert [m.content for m in store.history("skeptic")] == ["first"]


def test_append_to_unknown_seat_raises():
    store = SeatStore()

    with pytest.raises(UnknownSeatError):
        store.append("nonexistent", Message(role="user", content="hi"))


def test_history_of_unknown_seat_raises():
    store = SeatStore()

    with pytest.raises(UnknownSeatError):
        store.history("nonexistent")


def test_seats_lists_registered_ids_in_registration_order():
    store = SeatStore()
    store.register("reframer")
    store.register("skeptic")
    store.register("generator")

    assert store.seats() == ["reframer", "skeptic", "generator"]
