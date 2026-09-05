"""The core debate loop: user seed -> independent takes -> reveal -> cross-critique
rounds with the uptake rule enforced -> disagreement map.

See docs/DESIGN.md section 5 for the protocol this implements, and CLAUDE.md's
non-negotiable principles 2-5 for what each piece here is defending against.

This module is the engine's orchestration; it does not do any actual terminal I/O.
"User seed" is just a string passed to `DebateSession`; "the user may interject at
any point" (docs/DESIGN.md section 5, step 7) and "the user picks or edits" a
reframe (section 3) are both real MVP requirements but real human interaction, so
both are exposed as extension points here (`choose_framing` on `run_reframe`; the
round-by-round structure of `run` itself, callable stepwise) for milestone 6's CLI
to drive, rather than guessed at without a consumer.

The engine stays technique-agnostic (CLAUDE.md principle 1): the only thing it
knows about the intervention layer is the `Hook` vocabulary and an optional
`InterventionPolicy` to fire hooks against. Three of the four hooks fire on
signals the engine already has: `ON_PHASE_CHANGE` on every phase transition
(certain, since phases always alternate), `ON_EARLY_NARROWING` when a turn's
target repeats one already raised, and `ON_FALSE_CONSENSUS` when a round has no
rebuttal at all. `ON_USER_STALL` is defined but never fired here: it's about the
human user stalling, which needs real terminal I/O that doesn't exist until
milestone 6. `policy=None` (the default) skips all of this, so a session behaves
exactly as it did before this existed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..intervention import Hook, HookEvent, InterventionPolicy, MoveContext
from ..providers import get_adapter
from ..providers.base import Message, ProviderAdapter
from ..state import SeatStore
from .conductor import DisagreementMap, StallJudgment, build_disagreement_map, check_stalled
from .map import build_skeleton
from .reframe import REFRAME_PROMPT, parse_framings
from .seats import SeatConfig
from .turns import Phase, Stance, Turn
from .uptake import CORRECTIVE_NUDGE, UPTAKE_FORMAT_INSTRUCTIONS, parse_uptake

PHASE_INSTRUCTIONS: dict[Phase, str] = {
    Phase.EXPAND: (
        "This round, favor expanding: build on what's strong, explore implications "
        "and adjacent possibilities, and only push back where something seems "
        "genuinely weak."
    ),
    Phase.STRESS_TEST: (
        "This round, favor stress-testing: look hard for weaknesses, unstated "
        "assumptions, or failure modes, and press on them rigorously."
    ),
}


@dataclass(frozen=True)
class DebateResult:
    transcript: list[Turn]
    disagreement_map: DisagreementMap
    rounds_run: int
    stop_reason: str  # "stalled" | "max_rounds"
    stall_judgments: list[StallJudgment]
    hook_events: list[HookEvent]


class DebateSession:
    def __init__(
        self,
        seed: str,
        debaters: tuple[SeatConfig, SeatConfig],
        conductor: SeatConfig,
        reframer: SeatConfig | None = None,
        max_rounds: int = 8,
        adapters: dict[str, ProviderAdapter] | None = None,
        policy: InterventionPolicy | None = None,
    ) -> None:
        self.seed = seed
        self.debater_a, self.debater_b = debaters
        self.conductor = conductor
        self.reframer = reframer
        self.max_rounds = max_rounds
        self.policy = policy

        self.store = SeatStore()
        self.store.register(self.debater_a.seat_id)
        self.store.register(self.debater_b.seat_id)

        self.transcript: list[Turn] = []
        self.stall_judgments: list[StallJudgment] = []
        self.hook_events: list[HookEvent] = []

        self._adapters: dict[str, ProviderAdapter] = dict(adapters or {})

    # --- provider lookup ---------------------------------------------------------

    def _adapter_for(self, seat: SeatConfig) -> ProviderAdapter:
        if seat.provider not in self._adapters:
            self._adapters[seat.provider] = get_adapter(seat.provider)
        return self._adapters[seat.provider]

    def _call(self, seat: SeatConfig) -> str:
        adapter = self._adapter_for(seat)
        response = adapter.generate(
            self.store.history(seat.seat_id),
            model=seat.model,
            system=seat.system_prompt,
            max_tokens=seat.max_tokens,
            temperature=seat.temperature,
        )
        return response.text

    def _other_debater(self, seat: SeatConfig) -> SeatConfig:
        return self.debater_b if seat.seat_id == self.debater_a.seat_id else self.debater_a

    def _find_turn(self, seat_id: str, round_index: int) -> Turn:
        for turn in self.transcript:
            if turn.seat_id == seat_id and turn.round_index == round_index:
                return turn
        raise LookupError(f"no turn for seat {seat_id!r} at round {round_index}")

    # --- hooks (see this module's docstring for what fires and why) --------------

    def _fire(self, hook: Hook, round_index: int, prior_targets: list[str]) -> None:
        if self.policy is None:
            return
        context = MoveContext(seed=self.seed, seat_id="", recent_targets=tuple(prior_targets))
        self.hook_events.append(self.policy.fire(hook, context, round_index))

    def _fire_round_hooks(self, turns: tuple[Turn, Turn], round_index: int, prior_targets: list[str]) -> None:
        """`prior_targets` here is the list as of *before* this round's own
        targets are added, since "does this repeat something earlier" only makes
        sense against what came before it."""
        seen = {t.strip().lower() for t in prior_targets}
        if any(t.target and t.target.strip().lower() in seen for t in turns):
            self._fire(Hook.ON_EARLY_NARROWING, round_index, prior_targets)

        if not any(t.stance is Stance.REBUT for t in turns):
            self._fire(Hook.ON_FALSE_CONSENSUS, round_index, prior_targets)

    # --- reframe (optional) -------------------------------------------------------

    def run_reframe(self, choose_framing: Callable[[list[str]], str] | None = None) -> str | None:
        """Returns the chosen reframed problem, or None if there's no reframer seat
        or it failed to produce a parseable framing (the caller falls back to the
        raw seed either way)."""
        if self.reframer is None:
            return None

        adapter = self._adapter_for(self.reframer)
        prompt = REFRAME_PROMPT.format(seed=self.seed)
        response = adapter.generate(
            [Message(role="user", content=prompt)],
            model=self.reframer.model,
            system=self.reframer.system_prompt,
            max_tokens=self.reframer.max_tokens,
        )
        framings = parse_framings(response.text)
        if not framings:
            return None

        choose = choose_framing or (lambda options: options[0])
        return choose(framings)

    # --- independent takes + reveal -----------------------------------------------

    def run_independent_takes(self, problem: str) -> tuple[Turn, Turn]:
        """Each debater answers the same prompt without seeing the other's answer;
        their histories only ever contain their own conversation (SeatStore
        guarantees this, see state.py)."""
        turns = []
        for seat in (self.debater_a, self.debater_b):
            self.store.append(seat.seat_id, Message(role="user", content=problem))
            raw = self._call(seat)
            self.store.append(seat.seat_id, Message(role="assistant", content=raw))

            turn = Turn(seat_id=seat.seat_id, round_index=0, phase=None, text=raw, raw=raw)
            turns.append(turn)
            self.transcript.append(turn)
        return turns[0], turns[1]

    # --- cross-critique rounds (uptake enforced) -----------------------------------

    def _critique_prompt(self, seat: SeatConfig, phase: Phase, round_index: int) -> str:
        predecessor = self._find_turn(self._other_debater(seat).seat_id, round_index - 1)
        return (
            f"{PHASE_INSTRUCTIONS[phase]}\n\n"
            f'Here is what the other debater said:\n\n"{predecessor.text}"\n\n'
            f"{UPTAKE_FORMAT_INSTRUCTIONS}"
        )

    def _generate_with_uptake(self, seat: SeatConfig, round_index: int, phase: Phase) -> Turn:
        raw = self._call(seat)
        parsed = parse_uptake(raw)

        if not parsed.ok:
            # One corrective retry (docs/DECISIONS.md D5: "validate it if feasible").
            # The flawed response is appended first so the seat's own history stays a
            # faithful record of what actually happened, and so the model sees its
            # own attempt for context on the retry.
            self.store.append(seat.seat_id, Message(role="assistant", content=raw))
            self.store.append(seat.seat_id, Message(role="user", content=CORRECTIVE_NUDGE))
            raw = self._call(seat)
            parsed = parse_uptake(raw)

        self.store.append(seat.seat_id, Message(role="assistant", content=raw))

        return Turn(
            seat_id=seat.seat_id,
            round_index=round_index,
            phase=phase,
            text=parsed.argument or raw,
            target=parsed.target,
            stance=parsed.stance,
            uptake_ok=parsed.ok,
            raw=raw,
        )

    def run_round(self, round_index: int, phase: Phase) -> tuple[Turn, Turn]:
        """Both debaters respond to the *other's* previous-round turn, each computed
        from state as of the end of the previous round, before either sees the
        other's response this round, so neither anchors on the other mid-round."""
        turns = []
        for seat in (self.debater_a, self.debater_b):
            prompt = self._critique_prompt(seat, phase, round_index)
            self.store.append(seat.seat_id, Message(role="user", content=prompt))
            turn = self._generate_with_uptake(seat, round_index, phase)
            turns.append(turn)
            self.transcript.append(turn)
        return turns[0], turns[1]

    # --- disagreement map -----------------------------------------------------------

    def build_map(self) -> DisagreementMap:
        skeleton = build_skeleton(self.transcript, (self.debater_a.seat_id, self.debater_b.seat_id))
        return build_disagreement_map(self._adapter_for(self.conductor), self.conductor, skeleton)

    # --- full run ---------------------------------------------------------------

    def run(self, choose_framing: Callable[[list[str]], str] | None = None) -> DebateResult:
        problem = self.run_reframe(choose_framing) or self.seed
        self.run_independent_takes(problem)

        prior_targets: list[str] = []
        phase = Phase.EXPAND
        round_index = 1
        stop_reason = "max_rounds"

        while round_index <= self.max_rounds:
            turns = self.run_round(round_index, phase)
            self._fire_round_hooks(turns, round_index, prior_targets)

            judgment = check_stalled(self._adapter_for(self.conductor), self.conductor, list(turns), prior_targets)
            self.stall_judgments.append(judgment)
            prior_targets.extend(t.target for t in turns if t.target)

            if judgment.stalled:
                stop_reason = "stalled"
                break

            round_index += 1
            phase = phase.next()
            if round_index <= self.max_rounds:
                # Don't announce a phase change for a round that won't actually run.
                self._fire(Hook.ON_PHASE_CHANGE, round_index, prior_targets)

        return DebateResult(
            transcript=list(self.transcript),
            disagreement_map=self.build_map(),
            rounds_run=min(round_index, self.max_rounds),
            stop_reason=stop_reason,
            stall_judgments=list(self.stall_judgments),
            hook_events=list(self.hook_events),
        )
