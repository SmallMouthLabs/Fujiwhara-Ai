from __future__ import annotations

import pytest
from conftest import FakeAdapter

from debate_tool.engine import DebateSession, Phase, SeatConfig, Stance
from debate_tool.intervention import Hook, InterventionPolicy, Move

DEBATER_A = SeatConfig(seat_id="skeptic", provider="prov-a", model="model-a", system_prompt="You are the skeptic.")
DEBATER_B = SeatConfig(
    seat_id="generator", provider="prov-b", model="model-b", system_prompt="You are the generator."
)
CONDUCTOR = SeatConfig(seat_id="conductor", provider="prov-c", model="model-c", system_prompt="You run the room.")
REFRAMER = SeatConfig(seat_id="reframer", provider="prov-r", model="model-r", system_prompt="You reframe.")

SEED = "Should we build feature X?"


def well_formed(target: str, stance: str, argument: str) -> str:
    return f"TARGET: {target}\nSTANCE: {stance}\nARGUMENT: {argument}"


def make_session(
    *, adapter_a, adapter_b, adapter_c, max_rounds=8, min_rounds=2, reframer=None, adapter_r=None, policy=None
):
    adapters = {"prov-a": adapter_a, "prov-b": adapter_b, "prov-c": adapter_c}
    if reframer is not None:
        adapters["prov-r"] = adapter_r
    return DebateSession(
        seed=SEED,
        debaters=(DEBATER_A, DEBATER_B),
        conductor=CONDUCTOR,
        reframer=reframer,
        max_rounds=max_rounds,
        min_rounds=min_rounds,
        adapters=adapters,
        policy=policy,
    )


# --- independent takes ---------------------------------------------------------


def test_independent_takes_are_recorded_and_isolated():
    adapter_a = FakeAdapter(["skeptic's opening take"])
    adapter_b = FakeAdapter(["generator's opening take"])
    session = make_session(adapter_a=adapter_a, adapter_b=adapter_b, adapter_c=FakeAdapter([]))

    turn_a, turn_b = session.run_independent_takes(session.seed)

    assert (turn_a.seat_id, turn_a.text, turn_a.round_index, turn_a.stance) == ("skeptic", "skeptic's opening take", 0, None)
    assert turn_b.text == "generator's opening take"

    # both seats got the exact same seed as their first message
    assert adapter_a.calls[0]["messages"][0].content == SEED
    assert adapter_b.calls[0]["messages"][0].content == SEED

    # isolation: each seat's own history holds only its own turn
    assert [m.content for m in session.store.history("skeptic")] == [SEED, "skeptic's opening take"]
    assert [m.content for m in session.store.history("generator")] == [SEED, "generator's opening take"]


# --- reveal + round prompt -------------------------------------------------------


def test_round_prompt_reveals_only_the_other_seats_previous_turn():
    adapter_a = FakeAdapter(["skeptic opening", well_formed("generator opening", "rebut", "a's rebuttal")])
    adapter_b = FakeAdapter(["generator opening", well_formed("skeptic opening", "extend", "b's extension")])
    session = make_session(adapter_a=adapter_a, adapter_b=adapter_b, adapter_c=FakeAdapter([]))

    session.run_independent_takes(SEED)
    turn_a, turn_b = session.run_round(1, Phase.EXPAND)

    prompt_to_a = adapter_a.calls[1]["messages"][-1].content
    assert "generator opening" in prompt_to_a
    assert "skeptic opening" not in prompt_to_a  # A's own prior take isn't shown back as "the other debater"

    prompt_to_b = adapter_b.calls[1]["messages"][-1].content
    assert "skeptic opening" in prompt_to_b

    assert (turn_a.stance, turn_a.target, turn_a.text) == (Stance.REBUT, "generator opening", "a's rebuttal")


# --- uptake enforcement (retry-once) ---------------------------------------------


def test_malformed_response_triggers_one_retry_and_succeeds():
    adapter_a = FakeAdapter(
        [
            "skeptic opening",
            "this is not in the right format at all",
            well_formed("generator opening", "extend", "corrected argument"),
        ]
    )
    adapter_b = FakeAdapter(["generator opening", well_formed("skeptic opening", "extend", "b's argument")])
    session = make_session(adapter_a=adapter_a, adapter_b=adapter_b, adapter_c=FakeAdapter([]))

    session.run_independent_takes(SEED)
    turn_a, _ = session.run_round(1, Phase.EXPAND)

    assert turn_a.uptake_ok is True
    assert turn_a.text == "corrected argument"
    assert len(adapter_a.calls) == 3  # opening, malformed attempt, retry

    history = session.store.history("skeptic")
    # [0]=seed, [1]=opening take, [2]=round-1 critique prompt, then the retry dance:
    assert history[3].role == "assistant" and history[3].content == "this is not in the right format at all"
    assert history[4].role == "user" and "didn't follow the required format" in history[4].content
    assert history[5].role == "assistant" and "corrected argument" in history[5].content


def test_still_malformed_after_retry_is_flagged_and_not_retried_a_third_time():
    # Only 3 scripted responses: opening + two malformed attempts. A third call
    # would raise from FakeAdapter itself, so this also proves no further retry.
    adapter_a = FakeAdapter(["skeptic opening", "malformed one", "malformed two"])
    adapter_b = FakeAdapter(["generator opening", well_formed("skeptic opening", "extend", "b's argument")])
    session = make_session(adapter_a=adapter_a, adapter_b=adapter_b, adapter_c=FakeAdapter([]))

    session.run_independent_takes(SEED)
    turn_a, _ = session.run_round(1, Phase.EXPAND)

    assert turn_a.uptake_ok is False
    assert turn_a.text == "malformed two"
    assert len(adapter_a.calls) == 3


# --- full run: phase oscillation + stall stop + max_rounds cap ------------------


def test_full_run_alternates_phase_and_stops_on_stall():
    adapter_a = FakeAdapter(
        [
            "skeptic opening",
            well_formed("generator opening", "extend", "a round1 arg"),
            well_formed("generator round1", "rebut", "a round2 arg"),
        ]
    )
    adapter_b = FakeAdapter(
        [
            "generator opening",
            well_formed("skeptic opening", "steelman", "b round1 arg"),
            well_formed("skeptic round1", "extend", "b round2 arg"),
        ]
    )
    adapter_c = FakeAdapter(
        [
            "STALLED: no\nREASON: round 1 raised new points.",
            "STALLED: yes\nREASON: round 2 just restates round 1.",
            "AGREEMENTS:\nthey converged\n\nSPLITS:\nthey split\n\nOPEN QUESTION:\nwhat now?",
        ]
    )
    session = make_session(adapter_a=adapter_a, adapter_b=adapter_b, adapter_c=adapter_c, max_rounds=8)

    result = session.run()

    assert result.stop_reason == "stalled"
    assert result.rounds_run == 2
    assert len(result.transcript) == 6  # 2 opening + 2 rounds x 2 turns
    assert len(adapter_c.calls) == 3  # stall check x2 + map prose

    round1_prompt = adapter_a.calls[1]["messages"][-1].content
    round2_prompt = adapter_a.calls[2]["messages"][-1].content
    assert "favor expanding" in round1_prompt
    assert "favor stress-testing" in round2_prompt

    assert result.disagreement_map.open_question_prose == "what now?"


def test_max_rounds_cap_stops_the_loop_even_if_never_stalled():
    responses_a = ["skeptic opening"] + [well_formed("x", "extend", f"a r{i}") for i in range(1, 4)]
    responses_b = ["generator opening"] + [well_formed("x", "extend", f"b r{i}") for i in range(1, 4)]
    adapter_a = FakeAdapter(responses_a)
    adapter_b = FakeAdapter(responses_b)
    adapter_c = FakeAdapter(
        ["STALLED: no\nREASON: fine."] * 3 + ["AGREEMENTS:\na\n\nSPLITS:\nb\n\nOPEN QUESTION:\nc"]
    )
    session = make_session(adapter_a=adapter_a, adapter_b=adapter_b, adapter_c=adapter_c, max_rounds=3)

    result = session.run()

    assert result.stop_reason == "max_rounds"
    assert result.rounds_run == 3
    assert len(adapter_a.calls) == 4  # opening + 3 rounds


# --- reframe --------------------------------------------------------------------


def test_reframe_default_picks_the_first_framing():
    adapter_r = FakeAdapter(["FRAMING: it's really about trust\nFRAMING: it's really about cost"])
    session = make_session(
        adapter_a=FakeAdapter([]),
        adapter_b=FakeAdapter([]),
        adapter_c=FakeAdapter([]),
        reframer=REFRAMER,
        adapter_r=adapter_r,
    )

    assert session.run_reframe() == "it's really about trust"


def test_reframe_uses_the_choose_framing_callback():
    adapter_r = FakeAdapter(["FRAMING: option one\nFRAMING: option two"])
    session = make_session(
        adapter_a=FakeAdapter([]),
        adapter_b=FakeAdapter([]),
        adapter_c=FakeAdapter([]),
        reframer=REFRAMER,
        adapter_r=adapter_r,
    )

    assert session.run_reframe(choose_framing=lambda options: options[1]) == "option two"


def test_reframe_returns_none_without_a_reframer_seat():
    session = make_session(adapter_a=FakeAdapter([]), adapter_b=FakeAdapter([]), adapter_c=FakeAdapter([]))

    assert session.run_reframe() is None


def test_reframe_returns_none_when_unparseable():
    adapter_r = FakeAdapter(["I don't have any framings for you."])
    session = make_session(
        adapter_a=FakeAdapter([]),
        adapter_b=FakeAdapter([]),
        adapter_c=FakeAdapter([]),
        reframer=REFRAMER,
        adapter_r=adapter_r,
    )

    assert session.run_reframe() is None


# --- intervention hooks (milestone 5) --------------------------------------------


def _no_rebuttal_responses(n_rounds: int) -> tuple[list[str], list[str]]:
    """n_rounds worth of well-formed EXTEND responses (no REBUT ever), for each seat."""
    a = ["skeptic opening"] + [well_formed("x", "extend", f"a r{i}") for i in range(1, n_rounds + 1)]
    b = ["generator opening"] + [well_formed("x", "extend", f"b r{i}") for i in range(1, n_rounds + 1)]
    return a, b


def test_no_policy_means_no_hook_events():
    a, b = _no_rebuttal_responses(2)
    adapter_c = FakeAdapter(
        ["STALLED: no\nREASON: fine."] * 2 + ["AGREEMENTS:\na\n\nSPLITS:\nb\n\nOPEN QUESTION:\nc"]
    )
    session = make_session(adapter_a=FakeAdapter(a), adapter_b=FakeAdapter(b), adapter_c=adapter_c, max_rounds=2)

    result = session.run()

    assert result.hook_events == []


def test_on_phase_change_fires_between_rounds_but_not_after_the_last_one():
    a, b = _no_rebuttal_responses(3)
    adapter_c = FakeAdapter(
        ["STALLED: no\nREASON: fine."] * 3 + ["AGREEMENTS:\na\n\nSPLITS:\nb\n\nOPEN QUESTION:\nc"]
    )
    move = Move(name="noop", when_to_use="always", template="noop for {seed}")
    policy = InterventionPolicy(moves={"noop": move}, mapping={Hook.ON_PHASE_CHANGE: ("noop",)})
    session = make_session(
        adapter_a=FakeAdapter(a), adapter_b=FakeAdapter(b), adapter_c=adapter_c, max_rounds=3, policy=policy
    )

    result = session.run()

    phase_changes = [e for e in result.hook_events if e.hook is Hook.ON_PHASE_CHANGE]
    # 3 rounds run -> 2 transitions (1->2, 2->3); no phase-change announced for a
    # round 4 that never runs.
    assert [e.round_index for e in phase_changes] == [2, 3]
    assert all(e.applied_moves == ("noop",) for e in phase_changes)
    assert all(e.rendered == (f"noop for {SEED}",) for e in phase_changes)


def test_on_false_consensus_fires_when_a_round_has_no_rebuttal():
    a, b = _no_rebuttal_responses(1)
    adapter_c = FakeAdapter(
        ["STALLED: yes\nREASON: done."] + ["AGREEMENTS:\na\n\nSPLITS:\nb\n\nOPEN QUESTION:\nc"]
    )
    policy = InterventionPolicy(moves={}, mapping={})
    # min_rounds=1 so the round-1 stall verdict ends the debate here; this test is
    # about the false-consensus hook firing, not the min-rounds floor.
    session = make_session(
        adapter_a=FakeAdapter(a),
        adapter_b=FakeAdapter(b),
        adapter_c=adapter_c,
        max_rounds=8,
        min_rounds=1,
        policy=policy,
    )

    result = session.run()

    false_consensus = [e for e in result.hook_events if e.hook is Hook.ON_FALSE_CONSENSUS]
    assert len(false_consensus) == 1
    assert false_consensus[0].round_index == 1
    assert false_consensus[0].applied_moves == ()  # no move registered, but the condition is still recorded


def test_on_early_narrowing_fires_when_a_target_repeats():
    adapter_a = FakeAdapter(
        [
            "skeptic opening",
            well_formed("generator opening", "extend", "a round1"),
            well_formed("generator opening", "extend", "a round2, same target again"),
        ]
    )
    adapter_b = FakeAdapter(
        [
            "generator opening",
            well_formed("skeptic opening", "extend", "b round1"),
            well_formed("skeptic round1", "extend", "b round2"),
        ]
    )
    adapter_c = FakeAdapter(
        [
            "STALLED: no\nREASON: fine.",
            "STALLED: yes\nREASON: done.",
            "AGREEMENTS:\na\n\nSPLITS:\nb\n\nOPEN QUESTION:\nc",
        ]
    )
    policy = InterventionPolicy(moves={}, mapping={})
    session = make_session(
        adapter_a=adapter_a, adapter_b=adapter_b, adapter_c=adapter_c, max_rounds=8, policy=policy
    )

    result = session.run()

    narrowing = [e for e in result.hook_events if e.hook is Hook.ON_EARLY_NARROWING]
    assert len(narrowing) == 1
    assert narrowing[0].round_index == 2  # round 2's "a" turn re-targets round 1's target


# --- run() callbacks: progress and interjection (milestone 6's seam) -------------


def test_on_event_fires_expected_progress_points_in_order():
    adapter_a = FakeAdapter(["skeptic opening", well_formed("generator opening", "rebut", "a round1")])
    adapter_b = FakeAdapter(["generator opening", well_formed("skeptic opening", "extend", "b round1")])
    adapter_c = FakeAdapter(["STALLED: yes\nREASON: done.", "AGREEMENTS:\na\n\nSPLITS:\nb\n\nOPEN QUESTION:\nc"])
    session = make_session(adapter_a=adapter_a, adapter_b=adapter_b, adapter_c=adapter_c, min_rounds=1)

    events: list[tuple[str, dict]] = []
    session.run(on_event=lambda name, payload: events.append((name, payload)))

    names = [name for name, _ in events]
    assert names == ["problem_set", "independent_take", "independent_take", "map_done"]
    assert events[0][1]["problem"] == SEED
    assert events[1][1]["turn"].seat_id == "skeptic"
    assert events[2][1]["turn"].seat_id == "generator"
    assert events[3][1]["disagreement_map"].open_question_prose == "c"


def test_on_round_end_can_force_a_stop_even_when_not_judged_stalled():
    adapter_a = FakeAdapter(
        ["skeptic opening"]
        + [well_formed("x", "extend", f"a r{i}") for i in range(1, 4)]
    )
    adapter_b = FakeAdapter(
        ["generator opening"]
        + [well_formed("x", "extend", f"b r{i}") for i in range(1, 4)]
    )
    # Only one "no" scripted: if the engine ran a second round despite the forced
    # stop, this adapter would raise for lack of a scripted response.
    adapter_c = FakeAdapter(["STALLED: no\nREASON: fine.", "AGREEMENTS:\na\n\nSPLITS:\nb\n\nOPEN QUESTION:\nc"])
    session = make_session(adapter_a=adapter_a, adapter_b=adapter_b, adapter_c=adapter_c, max_rounds=8)

    result = session.run(on_round_end=lambda *_: "stop")

    assert result.stop_reason == "user"
    assert result.rounds_run == 1
    assert len(adapter_a.calls) == 2  # opening + round 1 only


def test_on_round_end_can_force_continuing_past_a_stalled_judgment():
    adapter_a = FakeAdapter(
        ["skeptic opening", well_formed("x", "extend", "a r1"), well_formed("x", "extend", "a r2")]
    )
    adapter_b = FakeAdapter(
        ["generator opening", well_formed("x", "extend", "b r1"), well_formed("x", "extend", "b r2")]
    )
    adapter_c = FakeAdapter(
        [
            "STALLED: yes\nREASON: looks stalled.",  # round 1: judged stalled, but overridden
            "STALLED: yes\nREASON: still stalled.",  # round 2: judged stalled, deferred (not overridden)
            "AGREEMENTS:\na\n\nSPLITS:\nb\n\nOPEN QUESTION:\nc",
        ]
    )
    session = make_session(adapter_a=adapter_a, adapter_b=adapter_b, adapter_c=adapter_c, max_rounds=8)

    calls = []

    def on_round_end(_session, _turns, round_index, judgment):
        calls.append((round_index, judgment.stalled))
        return "continue" if round_index == 1 else None

    result = session.run(on_round_end=on_round_end)

    assert calls == [(1, True), (2, True)]
    assert result.rounds_run == 2
    assert result.stop_reason == "stalled"


def test_on_round_end_can_inject_a_message_into_both_debaters_histories():
    adapter_a = FakeAdapter(
        ["skeptic opening", well_formed("x", "extend", "a r1"), well_formed("x", "extend", "a r2")]
    )
    adapter_b = FakeAdapter(
        ["generator opening", well_formed("x", "extend", "b r1"), well_formed("x", "extend", "b r2")]
    )
    adapter_c = FakeAdapter(
        ["STALLED: no\nREASON: fine.", "STALLED: yes\nREASON: done.", "AGREEMENTS:\na\n\nSPLITS:\nb\n\nOPEN QUESTION:\nc"]
    )
    session = make_session(adapter_a=adapter_a, adapter_b=adapter_b, adapter_c=adapter_c, max_rounds=8)

    def inject_once(sess, _turns, round_index, _judgment):
        if round_index == 1:
            from debate_tool.providers.base import Message

            sess.store.append(sess.debater_a.seat_id, Message(role="user", content="a user interjection"))
            sess.store.append(sess.debater_b.seat_id, Message(role="user", content="a user interjection"))
        return None

    session.run(on_round_end=inject_once)

    history_a = session.store.history("skeptic")
    injected = [m for m in history_a if m.content == "a user interjection"]
    assert len(injected) == 1
    # it lands after round 1's exchange and before round 2's critique prompt
    injected_index = history_a.index(injected[0])
    assert history_a[injected_index - 1].role == "assistant"  # round 1's own response
    assert history_a[injected_index + 1].role == "user"  # round 2's critique prompt


def test_run_twice_on_same_session_is_rejected():
    adapter_a = FakeAdapter(["skeptic opening", well_formed("generator opening", "rebut", "a round1")])
    adapter_b = FakeAdapter(["generator opening", well_formed("skeptic opening", "extend", "b round1")])
    adapter_c = FakeAdapter(["STALLED: yes\nREASON: done.", "AGREEMENTS:\na\n\nSPLITS:\nb\n\nOPEN QUESTION:\nc"])
    session = make_session(adapter_a=adapter_a, adapter_b=adapter_b, adapter_c=adapter_c, min_rounds=1)

    session.run()

    with pytest.raises(RuntimeError, match="already run"):
        session.run()


# --- min_rounds floor: an auto-stall verdict isn't honored too early (Q4) --------


def test_round_one_stall_is_not_honored_by_default_min_rounds():
    # Round 1 is judged stalled, but the default floor (min_rounds=2) means the
    # debate proceeds to round 2 rather than ending on the first exchange.
    adapter_a = FakeAdapter(
        ["skeptic opening", well_formed("g", "rebut", "a r1"), well_formed("g", "rebut", "a r2")]
    )
    adapter_b = FakeAdapter(
        ["generator opening", well_formed("s", "extend", "b r1"), well_formed("s", "extend", "b r2")]
    )
    adapter_c = FakeAdapter(
        [
            "STALLED: yes\nREASON: premature round-1 verdict.",
            "STALLED: yes\nREASON: now genuinely stalled.",
            "AGREEMENTS:\na\n\nSPLITS:\nb\n\nOPEN QUESTION:\nc",
        ]
    )
    session = make_session(adapter_a=adapter_a, adapter_b=adapter_b, adapter_c=adapter_c, max_rounds=8)

    result = session.run()

    # round 1's stall was ignored; round 2's stall (>= min_rounds) ended it
    assert result.rounds_run == 2
    assert result.stop_reason == "stalled"
    # both rounds' judgments were still recorded, even the ignored one
    assert [j.stalled for j in result.stall_judgments] == [True, True]


def test_min_rounds_one_restores_round_one_stall_stopping():
    a, b = _no_rebuttal_responses(1)
    adapter_c = FakeAdapter(["STALLED: yes\nREASON: done.", "AGREEMENTS:\na\n\nSPLITS:\nb\n\nOPEN QUESTION:\nc"])
    session = make_session(
        adapter_a=FakeAdapter(a), adapter_b=FakeAdapter(b), adapter_c=adapter_c, max_rounds=8, min_rounds=1
    )

    result = session.run()

    assert result.rounds_run == 1
    assert result.stop_reason == "stalled"


def test_explicit_user_stop_is_honored_even_before_min_rounds():
    # The floor only gates the *automatic* stall; a user's explicit stop wins at
    # round 1 regardless.
    a, b = _no_rebuttal_responses(1)
    adapter_c = FakeAdapter(["STALLED: no\nREASON: fine.", "AGREEMENTS:\na\n\nSPLITS:\nb\n\nOPEN QUESTION:\nc"])
    session = make_session(
        adapter_a=FakeAdapter(a), adapter_b=FakeAdapter(b), adapter_c=adapter_c, max_rounds=8, min_rounds=5
    )

    result = session.run(on_round_end=lambda *_: "stop")

    assert result.rounds_run == 1
    assert result.stop_reason == "user"


def test_min_rounds_is_clamped_to_max_rounds():
    # min_rounds greater than max_rounds must not deadlock the loop; it's clamped
    # to max_rounds so the loop always terminates (here via the max_rounds cap).
    a, b = _no_rebuttal_responses(1)
    adapter_c = FakeAdapter(["STALLED: no\nREASON: fine.", "AGREEMENTS:\na\n\nSPLITS:\nb\n\nOPEN QUESTION:\nc"])
    session = make_session(
        adapter_a=FakeAdapter(a), adapter_b=FakeAdapter(b), adapter_c=adapter_c, max_rounds=1, min_rounds=9
    )

    assert session.min_rounds == 1
    result = session.run()
    assert result.rounds_run == 1
    assert result.stop_reason == "max_rounds"
