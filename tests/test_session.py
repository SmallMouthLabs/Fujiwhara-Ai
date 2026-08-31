from __future__ import annotations

from conftest import FakeAdapter

from debate_tool.engine import DebateSession, Phase, SeatConfig, Stance

DEBATER_A = SeatConfig(seat_id="skeptic", provider="prov-a", model="model-a", system_prompt="You are the skeptic.")
DEBATER_B = SeatConfig(
    seat_id="generator", provider="prov-b", model="model-b", system_prompt="You are the generator."
)
CONDUCTOR = SeatConfig(seat_id="conductor", provider="prov-c", model="model-c", system_prompt="You run the room.")
REFRAMER = SeatConfig(seat_id="reframer", provider="prov-r", model="model-r", system_prompt="You reframe.")

SEED = "Should we build feature X?"


def well_formed(target: str, stance: str, argument: str) -> str:
    return f"TARGET: {target}\nSTANCE: {stance}\nARGUMENT: {argument}"


def make_session(*, adapter_a, adapter_b, adapter_c, max_rounds=8, reframer=None, adapter_r=None):
    adapters = {"prov-a": adapter_a, "prov-b": adapter_b, "prov-c": adapter_c}
    if reframer is not None:
        adapters["prov-r"] = adapter_r
    return DebateSession(
        seed=SEED,
        debaters=(DEBATER_A, DEBATER_B),
        conductor=CONDUCTOR,
        reframer=reframer,
        max_rounds=max_rounds,
        adapters=adapters,
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
