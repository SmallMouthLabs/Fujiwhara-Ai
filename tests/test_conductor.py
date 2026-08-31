from __future__ import annotations

from conftest import FakeAdapter

from debate_tool.engine.conductor import build_disagreement_map, check_stalled
from debate_tool.engine.map import MapSkeleton, SkeletonEntry
from debate_tool.engine.seats import SeatConfig
from debate_tool.engine.turns import Phase, Stance, Turn

CONDUCTOR = SeatConfig(
    seat_id="conductor", provider="fake", model="conductor-model", system_prompt="You run the room."
)


def test_check_stalled_parses_yes():
    adapter = FakeAdapter(["STALLED: yes\nREASON: both sides are just restating round 1."])
    turn = Turn(seat_id="a", round_index=2, phase=Phase.STRESS_TEST, text="same point again", stance=Stance.REBUT)

    judgment = check_stalled(adapter, CONDUCTOR, [turn], prior_targets=["some earlier point"])

    assert judgment.stalled is True
    assert "restating" in judgment.reason


def test_check_stalled_parses_no():
    adapter = FakeAdapter(["STALLED: no\nREASON: a new failure mode was raised."])
    turn = Turn(seat_id="a", round_index=1, phase=Phase.EXPAND, text="a new point", stance=Stance.EXTEND)

    judgment = check_stalled(adapter, CONDUCTOR, [turn], prior_targets=[])

    assert judgment.stalled is False


def test_check_stalled_prompt_includes_prior_targets_and_latest_round():
    adapter = FakeAdapter(["STALLED: no\nREASON: fine."])
    turn = Turn(seat_id="a", round_index=1, phase=Phase.EXPAND, text="the actual argument text", stance=Stance.REBUT)

    check_stalled(adapter, CONDUCTOR, [turn], prior_targets=["an earlier target"])

    sent = adapter.calls[0]["messages"][0].content
    assert "an earlier target" in sent
    assert "the actual argument text" in sent


def test_build_disagreement_map_parses_three_sections():
    adapter = FakeAdapter(
        [
            "AGREEMENTS:\nBoth sides converged on point X.\n\n"
            "SPLITS:\nThey genuinely disagree about Y; A says one thing, B says another.\n\n"
            "OPEN QUESTION:\nShould you prioritize X or Y?"
        ]
    )
    skeleton = MapSkeleton(agreements=[], splits=[])

    result = build_disagreement_map(adapter, CONDUCTOR, skeleton)

    assert result.agreements_prose == "Both sides converged on point X."
    assert "disagree about Y" in result.splits_prose
    assert result.open_question_prose == "Should you prioritize X or Y?"
    assert result.skeleton is skeleton


def test_build_disagreement_map_prompt_is_grounded_in_the_skeleton_only():
    entry = SkeletonEntry(
        seat_id="a",
        round_index=1,
        stance=Stance.REBUT,
        target="b's claim",
        text="a's rebuttal text",
        predecessor_seat="b",
        predecessor_text="b's original claim",
    )
    skeleton = MapSkeleton(agreements=[], splits=[entry])
    adapter = FakeAdapter(["AGREEMENTS:\n(none)\n\nSPLITS:\nsummary\n\nOPEN QUESTION:\nq"])

    build_disagreement_map(adapter, CONDUCTOR, skeleton)

    sent = adapter.calls[0]["messages"][0].content
    assert "b's original claim" in sent
    assert "a's rebuttal text" in sent
    assert "Do not introduce any claim" in sent
