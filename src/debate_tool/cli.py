"""A minimal CLI that runs a full debate session end to end (milestone 6).

This is the thinnest layer that can drive `engine.session.DebateSession`
interactively: it loads config, wires the two callbacks `DebateSession.run`
exposes for exactly this purpose (`on_event` for progress, `on_round_end` for
real user interjection and the continue/stop decision) to the terminal, and
prints the final disagreement map. It contains no debate logic of its own; all
of that stays in the engine, per CLAUDE.md principle 1.

Run with `python -m debate_tool` or the `debate-tool` console script (see
pyproject.toml), from the repo root so the default config/ paths resolve.
"""

from __future__ import annotations

import argparse
import os
import sys
import textwrap
from pathlib import Path

from . import env
from .engine.conductor import StallJudgment
from .engine.session import DebateResult, DebateSession
from .engine.turns import Turn
from .intervention.policy import PolicyConfigError, load_moves, load_policy
from .persona_config import PersonaConfigError, PersonaSet, load_persona_set
from .providers.base import Message, ProviderError

WIDTH = 88

#: Which environment variable each provider's API key comes from, so a missing
#: key is caught before any API call, with a message naming the actual fix,
#: rather than surfacing as a raw SDK error mid-debate.
PROVIDER_ENV_VARS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}


def _wrap(text: str, indent: str = "") -> str:
    return textwrap.fill(text, width=WIDTH, initial_indent=indent, replace_whitespace=False)


def _print_heading(title: str) -> None:
    print(f"\n=== {title} ===")


def _missing_api_keys(persona_set: PersonaSet) -> list[str]:
    seats = [persona_set.debater_skeptic, persona_set.debater_generator, persona_set.conductor]
    if persona_set.reframer is not None:
        seats.append(persona_set.reframer)

    missing = []
    for seat in seats:
        env_var = PROVIDER_ENV_VARS.get(seat.provider)
        if env_var and not os.environ.get(env_var):
            missing.append(f"{seat.seat_id} needs {env_var} (provider {seat.provider!r})")
    return missing


def _choose_framing(options: list[str]) -> str:
    _print_heading("The reframer offers these alternate framings")
    for i, option in enumerate(options, start=1):
        print(_wrap(f"{i}. {option}"))
    raw = input(
        "\nPick a number, press Enter for the first, or type your own framing to use instead: "
    ).strip()
    if not raw:
        return options[0]
    if raw.isdigit() and 1 <= int(raw) <= len(options):
        return options[int(raw) - 1]
    return raw  # "or edits one" (docs/DESIGN.md section 3): a free-typed framing


def _print_turn(turn: Turn) -> None:
    label = turn.seat_id
    if turn.stance is not None:
        label += f" ({turn.stance.value}, re: \"{turn.target or '(no target given)'}\")"
        if not turn.uptake_ok:
            label += " [did not follow the uptake format]"
    print(f"\n--- {label} ---")
    print(_wrap(turn.text))


def _on_event(name: str, payload: dict) -> None:
    if name == "problem_set":
        _print_heading("Problem")
        print(_wrap(payload["problem"]))
    elif name == "independent_take":
        _print_turn(payload["turn"])
    # "map_done" is handled by _print_result after run() returns, not here.


def _print_judgment(judgment: StallJudgment) -> None:
    verdict = "looks stalled" if judgment.stalled else "still moving"
    print(f"\nConductor's read: {verdict}, {judgment.reason}")


def _make_on_round_end(auto: bool):
    def on_round_end(session: DebateSession, turns: tuple[Turn, Turn], round_index: int, judgment: StallJudgment):
        _print_heading(f"Round {round_index}")
        for turn in turns:
            _print_turn(turn)
        _print_judgment(judgment)

        if auto:
            return None

        while True:
            raw = input(
                "\n[Enter] continue automatically  [s] stop now  "
                "[c] force continue  [i] interject a note: "
            ).strip().lower()
            if raw == "":
                return None
            if raw == "s":
                return "stop"
            if raw == "c":
                return "continue"
            if raw == "i":
                note = input("Your note (goes to both debaters as-is): ").strip()
                if note:
                    for seat_id in (session.debater_a.seat_id, session.debater_b.seat_id):
                        session.store.append(seat_id, Message(role="user", content=note))
                keep_going = input("Continue after that? [Y/n]: ").strip().lower()
                return "stop" if keep_going == "n" else "continue"
            print(f"Didn't understand {raw!r}; try again.")

    return on_round_end


def _print_result(result: DebateResult) -> None:
    _print_heading(f"Disagreement map (stopped: {result.stop_reason}, {result.rounds_run} round(s))")
    dmap = result.disagreement_map
    print("\nAgreements:")
    print(_wrap(dmap.agreements_prose or "(none)", indent="  "))
    print("\nSplits:")
    print(_wrap(dmap.splits_prose or "(none)", indent="  "))
    print("\nOpen question for you to decide:")
    print(_wrap(dmap.open_question_prose or "(none)", indent="  "))


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="debate-tool",
        description="Two AI models debate your idea. You watch and decide.",
    )
    parser.add_argument("--seed", help="The idea to debate. Prompted for if omitted.")
    parser.add_argument("--config-dir", default="config", help="Directory holding personas/, moves/, policy.yaml.")
    parser.add_argument("--max-rounds", type=int, default=8, help="Hard cap on cross-critique rounds.")
    parser.add_argument(
        "--auto", action="store_true", help="Never prompt between rounds; run fully automatically."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    env.load()
    args = build_arg_parser().parse_args(argv)
    config_dir = Path(args.config_dir)

    try:
        persona_set = load_persona_set(config_dir / "personas")
    except PersonaConfigError as e:
        print(f"Persona config error: {e}", file=sys.stderr)
        return 1

    missing_keys = _missing_api_keys(persona_set)
    if missing_keys:
        print("Missing API key(s):", file=sys.stderr)
        for line in missing_keys:
            print(f"  - {line}", file=sys.stderr)
        print("Set them in .env (see .env.example) and try again.", file=sys.stderr)
        return 1

    try:
        moves = load_moves(config_dir / "moves")
        policy_path = config_dir / "policy.yaml"
        policy = load_policy(policy_path, moves) if policy_path.exists() else None
    except PolicyConfigError as e:
        print(f"Intervention policy config error: {e}", file=sys.stderr)
        return 1

    seed = args.seed or input("What idea do you want the models to debate?\n> ").strip()
    if not seed:
        print("No seed idea given.", file=sys.stderr)
        return 1

    session = DebateSession(
        seed=seed,
        max_rounds=args.max_rounds,
        policy=policy,
        **persona_set.as_session_kwargs(),
    )

    # Under --auto, don't block on input() for the reframe choice either: pass no
    # callback at all, which falls back to run_reframe's own default (the first
    # framing), the same as run_round's interjection prompts are skipped.
    choose_framing = None if args.auto else _choose_framing

    try:
        result = session.run(
            choose_framing=choose_framing,
            on_event=_on_event,
            on_round_end=_make_on_round_end(auto=args.auto),
        )
    except ProviderError as e:
        print(f"\nA model provider call failed: {e}", file=sys.stderr)
        return 1

    _print_result(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
