from __future__ import annotations

from debate_tool.engine.map import build_skeleton
from debate_tool.engine.turns import Phase, Stance, Turn


def _turn(seat_id, round_index, text, stance=None, target=None, phase=None):
    return Turn(
        seat_id=seat_id,
        round_index=round_index,
        phase=phase,
        text=text,
        target=target,
        stance=stance,
        uptake_ok=True,
        raw=text,
    )


def test_opening_takes_are_excluded_from_the_skeleton():
    transcript = [
        _turn("a", 0, "a's opening take"),
        _turn("b", 0, "b's opening take"),
    ]

    skeleton = build_skeleton(transcript, ("a", "b"))

    assert skeleton.agreements == []
    assert skeleton.splits == []


def test_steelman_and_extend_both_become_agreements_paired_with_the_right_predecessor():
    transcript = [
        _turn("a", 0, "a's opening take"),
        _turn("b", 0, "b's opening take"),
        _turn("a", 1, "a extends b's point", stance=Stance.EXTEND, target="b's point", phase=Phase.EXPAND),
        _turn("b", 1, "b steelmans a's point", stance=Stance.STEELMAN, target="a's point", phase=Phase.EXPAND),
    ]

    skeleton = build_skeleton(transcript, ("a", "b"))

    assert len(skeleton.agreements) == 2
    assert skeleton.splits == []

    a_entry = next(e for e in skeleton.agreements if e.seat_id == "a")
    assert a_entry.predecessor_seat == "b"
    assert a_entry.predecessor_text == "b's opening take"
    assert a_entry.target == "b's point"

    b_entry = next(e for e in skeleton.agreements if e.seat_id == "b")
    assert b_entry.predecessor_seat == "a"
    assert b_entry.predecessor_text == "a's opening take"


def test_rebut_becomes_a_split_paired_with_the_right_predecessor():
    transcript = [
        _turn("a", 0, "a's opening take"),
        _turn("b", 0, "b's opening take"),
        _turn("a", 1, "a rebuts b's point", stance=Stance.REBUT, target="b's point", phase=Phase.STRESS_TEST),
        _turn("b", 1, "b extends a's point", stance=Stance.EXTEND, target="a's point", phase=Phase.STRESS_TEST),
    ]

    skeleton = build_skeleton(transcript, ("a", "b"))

    assert len(skeleton.splits) == 1
    split = skeleton.splits[0]
    assert split.seat_id == "a"
    assert split.predecessor_seat == "b"
    assert split.predecessor_text == "b's opening take"
    assert split.stance is Stance.REBUT

    assert len(skeleton.agreements) == 1


def test_multi_round_chain_pairs_each_turn_with_its_actual_predecessor_not_positional_neighbor():
    """Round-r turns for both seats are generated independently from round r-1, so a
    flat-transcript adjacency heuristic would mis-pair them; this must key off
    (seat_id, round_index) instead."""
    transcript = [
        _turn("a", 0, "a opening"),
        _turn("b", 0, "b opening"),
        _turn("a", 1, "a round1", stance=Stance.EXTEND, target="b opening's point"),
        _turn("b", 1, "b round1", stance=Stance.REBUT, target="a opening's point"),
        _turn("a", 2, "a round2", stance=Stance.REBUT, target="b round1's point"),
        _turn("b", 2, "b round2", stance=Stance.STEELMAN, target="a round1's point"),
    ]

    skeleton = build_skeleton(transcript, ("a", "b"))

    a_round2 = next(e for e in skeleton.splits if e.seat_id == "a" and e.round_index == 2)
    assert a_round2.predecessor_seat == "b"
    assert a_round2.predecessor_text == "b round1"

    b_round2 = next(e for e in skeleton.agreements if e.seat_id == "b" and e.round_index == 2)
    assert b_round2.predecessor_seat == "a"
    assert b_round2.predecessor_text == "a round1"


def test_missing_predecessor_is_skipped_not_a_crash():
    transcript = [_turn("a", 1, "a round1 with no predecessor on record", stance=Stance.EXTEND, target="x")]

    skeleton = build_skeleton(transcript, ("a", "b"))

    assert skeleton.agreements == []
    assert skeleton.splits == []
