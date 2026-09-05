from __future__ import annotations

from types import SimpleNamespace

import pytest
from conftest import FakeAdapter

from debate_tool import cli
from debate_tool.engine.conductor import StallJudgment
from debate_tool.engine.turns import Phase, Stance, Turn
from debate_tool.persona_config import PersonaSet
from debate_tool.providers.base import Message


def seat(seat_id: str, provider: str) -> SimpleNamespace:
    return SimpleNamespace(seat_id=seat_id, provider=provider)


# --- argument parsing ------------------------------------------------------------


def test_arg_parser_defaults():
    args = cli.build_arg_parser().parse_args([])

    assert args.seed is None
    assert args.config_dir == "config"
    assert args.max_rounds == 8
    assert args.auto is False


def test_arg_parser_overrides():
    args = cli.build_arg_parser().parse_args(
        ["--seed", "an idea", "--config-dir", "other-config", "--max-rounds", "3", "--auto"]
    )

    assert args.seed == "an idea"
    assert args.config_dir == "other-config"
    assert args.max_rounds == 3
    assert args.auto is True


# --- API key preflight -------------------------------------------------------------


def make_persona_set(**providers: str) -> PersonaSet:
    return PersonaSet(
        debater_skeptic=seat("skeptic", providers.get("skeptic", "anthropic")),
        debater_generator=seat("generator", providers.get("generator", "openai")),
        conductor=seat("conductor", providers.get("conductor", "anthropic")),
        reframer=seat("reframer", providers["reframer"]) if "reframer" in providers else None,
    )


def test_missing_api_keys_reports_each_unset_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    persona_set = make_persona_set(reframer="anthropic")

    missing = cli._missing_api_keys(persona_set)

    assert len(missing) == 4  # skeptic, generator, conductor, reframer
    assert any("ANTHROPIC_API_KEY" in m for m in missing)
    assert any("OPENAI_API_KEY" in m for m in missing)


def test_missing_api_keys_empty_when_all_set(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    persona_set = make_persona_set()

    assert cli._missing_api_keys(persona_set) == []


def test_missing_api_keys_only_reports_seats_actually_used(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    persona_set = make_persona_set()  # no reframer

    missing = cli._missing_api_keys(persona_set)

    assert len(missing) == 1
    assert "generator" in missing[0]


# --- choose_framing (interactive reframe pick/edit) --------------------------------


def test_choose_framing_blank_input_picks_first(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt="": "")

    assert cli._choose_framing(["first", "second"]) == "first"


def test_choose_framing_numeric_input_picks_that_option(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt="": "2")

    assert cli._choose_framing(["first", "second"]) == "second"


def test_choose_framing_free_text_is_used_as_a_custom_framing(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt="": "my own framing")

    assert cli._choose_framing(["first", "second"]) == "my own framing"


# --- on_round_end (real user interjection) ------------------------------------------


def make_fake_session() -> SimpleNamespace:
    from debate_tool.state import SeatStore

    store = SeatStore()
    store.register("skeptic")
    store.register("generator")
    return SimpleNamespace(
        store=store,
        debater_a=SimpleNamespace(seat_id="skeptic"),
        debater_b=SimpleNamespace(seat_id="generator"),
    )


TURNS = (
    Turn(seat_id="skeptic", round_index=1, phase=Phase.EXPAND, text="a", target="t", stance=Stance.EXTEND),
    Turn(seat_id="generator", round_index=1, phase=Phase.EXPAND, text="b", target="t2", stance=Stance.REBUT),
)
JUDGMENT = StallJudgment(stalled=False, reason="fine")


def test_on_round_end_auto_never_prompts():
    on_round_end = cli._make_on_round_end(auto=True)

    # If this called input() under auto=True, it would raise (stdin isn't provided
    # in a test), so simply completing is itself the assertion.
    assert on_round_end(make_fake_session(), TURNS, 1, JUDGMENT) is None


def test_on_round_end_interactive_blank_defers(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    on_round_end = cli._make_on_round_end(auto=False)

    assert on_round_end(make_fake_session(), TURNS, 1, JUDGMENT) is None


def test_on_round_end_interactive_stop(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt="": "s")
    on_round_end = cli._make_on_round_end(auto=False)

    assert on_round_end(make_fake_session(), TURNS, 1, JUDGMENT) == "stop"


def test_on_round_end_interactive_force_continue(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt="": "c")
    on_round_end = cli._make_on_round_end(auto=False)

    assert on_round_end(make_fake_session(), TURNS, 1, JUDGMENT) == "continue"


def test_on_round_end_interactive_invalid_then_valid(monkeypatch):
    responses = iter(["bogus", "s"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(responses))
    on_round_end = cli._make_on_round_end(auto=False)

    assert on_round_end(make_fake_session(), TURNS, 1, JUDGMENT) == "stop"


def test_on_round_end_interject_appends_to_both_debaters_and_then_continues(monkeypatch):
    responses = iter(["i", "a user note", ""])  # "" -> Y/n default (continue)
    monkeypatch.setattr("builtins.input", lambda prompt="": next(responses))
    session = make_fake_session()
    on_round_end = cli._make_on_round_end(auto=False)

    decision = on_round_end(session, TURNS, 1, JUDGMENT)

    assert decision == "continue"
    assert Message(role="user", content="a user note") in session.store.history("skeptic")
    assert Message(role="user", content="a user note") in session.store.history("generator")


def test_on_round_end_interject_then_stop(monkeypatch):
    responses = iter(["i", "a user note", "n"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(responses))
    on_round_end = cli._make_on_round_end(auto=False)

    assert on_round_end(make_fake_session(), TURNS, 1, JUDGMENT) == "stop"


# --- full run, fake providers, no network call ---------------------------------------


def well_formed(target: str, stance: str, argument: str) -> str:
    return f"TARGET: {target}\nSTANCE: {stance}\nARGUMENT: {argument}"


def test_main_runs_a_full_auto_session_against_the_real_bundled_config(monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("OPENAI_API_KEY", "test")

    # config/personas/*.yaml puts skeptic, conductor, and reframer on "anthropic"
    # and generator on "openai"; one shared fake per provider, in the exact call
    # order session.run() makes them: reframe, skeptic opening, skeptic round 1,
    # stall check, disagreement map.
    anthropic_fake = FakeAdapter(
        [
            "FRAMING: the first framing\nFRAMING: a second framing",
            "skeptic's opening take",
            well_formed("generator's opening take", "rebut", "skeptic's round 1 argument"),
            "STALLED: no\nREASON: still developing.",
            "AGREEMENTS:\nthey agreed on something\n\n"
            "SPLITS:\nthey split on something\n\n"
            "OPEN QUESTION:\nwhat should you decide?",
        ]
    )
    openai_fake = FakeAdapter(
        [
            "generator's opening take",
            well_formed("skeptic's opening take", "extend", "generator's round 1 argument"),
        ]
    )

    def fake_get_adapter(provider: str):
        return {"anthropic": anthropic_fake, "openai": openai_fake}[provider]

    monkeypatch.setattr("debate_tool.engine.session.get_adapter", fake_get_adapter)

    exit_code = cli.main(["--seed", "Should we ship this?", "--auto", "--max-rounds", "1"])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Disagreement map" in out
    assert "what should you decide?" in out
    assert len(anthropic_fake.calls) == 5
    assert len(openai_fake.calls) == 2


def test_main_fails_fast_on_missing_api_keys(monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    exit_code = cli.main(["--seed", "an idea", "--auto"])

    assert exit_code == 1
    assert "Missing API key" in capsys.readouterr().err
