"""The disagreement map's skeleton: pure code, no LLM call.

Per docs/DECISIONS.md D12 (hybrid map generation), the skeleton (which points are
agreements, which are genuine splits, and each entry's grounding text on both sides)
is assembled entirely from the structured tags every cross-critique turn already
carries (`Turn.stance`, `Turn.target`). `conductor.py` layers one constrained LLM call
on top of this to produce prose; nothing in this module talks to a provider, which is
exactly why it's tested without one.

Each debater always responds to the *other* seat's turn from the previous round, or
its opening take for round 1; see `session.py`. That predecessor relationship is
looked up by `(seat_id, round_index)`, not by adjacency in the transcript list, since
both debaters' turns in a round are generated independently and appended in a fixed
order that doesn't itself encode who-responded-to-whom.
"""

from __future__ import annotations

from dataclasses import dataclass

from .turns import Stance, Turn


@dataclass(frozen=True)
class SkeletonEntry:
    seat_id: str
    round_index: int
    stance: Stance
    target: str | None
    text: str
    predecessor_seat: str
    predecessor_text: str


@dataclass(frozen=True)
class MapSkeleton:
    agreements: list[SkeletonEntry]
    splits: list[SkeletonEntry]


def build_skeleton(transcript: list[Turn], debater_ids: tuple[str, str]) -> MapSkeleton:
    by_key: dict[tuple[str, int], Turn] = {(t.seat_id, t.round_index): t for t in transcript}
    seat_a, seat_b = debater_ids

    agreements: list[SkeletonEntry] = []
    splits: list[SkeletonEntry] = []

    for turn in transcript:
        if turn.stance is None:
            continue  # opening take: no prior point yet, uptake rule doesn't apply

        other_seat = seat_b if turn.seat_id == seat_a else seat_a
        predecessor = by_key.get((other_seat, turn.round_index - 1))
        if predecessor is None:
            continue  # shouldn't happen given how session.py builds rounds, but don't crash the map over it

        entry = SkeletonEntry(
            seat_id=turn.seat_id,
            round_index=turn.round_index,
            stance=turn.stance,
            target=turn.target,
            text=turn.text,
            predecessor_seat=predecessor.seat_id,
            predecessor_text=predecessor.text,
        )
        if turn.stance is Stance.REBUT:
            splits.append(entry)
        else:  # STEELMAN or EXTEND both read as convergence on that point
            agreements.append(entry)

    return MapSkeleton(agreements=agreements, splits=splits)
