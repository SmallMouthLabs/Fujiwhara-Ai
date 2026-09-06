"""The conductor's two judgment calls: stall detection and the map's prose pass.

Both are deliberately narrow LLM calls layered on top of code-derived structure,
never free-form generation, so the "non-contributing conductor" principle
(CLAUDE.md principle 5, docs/DECISIONS.md D7) holds: the conductor extracts and
phrases what the debaters already said, and never adds an argument of its own.

The conductor is itself just a `SeatConfig` (see seats.py) pointed at whichever
provider/model you want judgment calls to run on; it has no persistent history in
`SeatStore`, since each call here is a fresh, single-shot analysis, not a
conversation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..providers.base import Message, ProviderAdapter
from ._parsing import label
from .map import MapSkeleton, SkeletonEntry
from .seats import SeatConfig
from .turns import Turn

# --- Stall detection (docs/DECISIONS.md D13) ------------------------------------

# Bold-label tolerance via `label()` (see _parsing.py), around the labels only;
# the captured REASON / map prose keeps any asterisks the model wrote.
_STALL_RE = re.compile(label("STALLED") + r"(yes|no)\b", re.IGNORECASE)
_STALL_REASON_RE = re.compile(label("REASON") + r"(.+)\Z", re.IGNORECASE | re.DOTALL)

_STALL_PROMPT = """
You are judging whether a debate has stalled: whether the latest round introduces
genuinely new arguments, or just restates points already made in earlier rounds.

Points already raised in earlier rounds (for reference only, not the thing to judge):
{prior_targets_block}

The latest round:
{latest_round_block}

Respond in exactly this format, nothing before or after it:

STALLED: yes or no
REASON: one sentence
""".strip()


@dataclass(frozen=True)
class StallJudgment:
    stalled: bool
    reason: str


def check_stalled(
    adapter: ProviderAdapter,
    conductor: SeatConfig,
    latest_round_turns: list[Turn],
    prior_targets: list[str],
) -> StallJudgment:
    prior_targets_block = "\n".join(f"- {t}" for t in prior_targets) or "(none yet)"
    latest_round_block = "\n\n".join(
        f"{t.seat_id} ({t.stance.value if t.stance else 'opening'}, "
        f"re: \"{t.target or '(no target given)'}\"): {t.text}"
        for t in latest_round_turns
    )
    prompt = _STALL_PROMPT.format(
        prior_targets_block=prior_targets_block, latest_round_block=latest_round_block
    )

    response = adapter.generate(
        [Message(role="user", content=prompt)],
        model=conductor.model,
        system=conductor.system_prompt,
        max_tokens=200,
    )

    stall_m = _STALL_RE.search(response.text)
    reason_m = _STALL_REASON_RE.search(response.text)
    stalled = bool(stall_m) and stall_m.group(1).lower() == "yes"
    reason = reason_m.group(1).strip() if reason_m else response.text.strip()
    return StallJudgment(stalled=stalled, reason=reason)


# --- Disagreement map prose pass (docs/DECISIONS.md D12) ------------------------

_MAP_PROMPT = """
You are turning a debate's already-extracted structure into readable prose for the
user. Do not introduce any claim, agreement, split, or consideration that is not
already given below. Only phrase, group, and summarize what is provided.

AGREEMENTS (a debater steelmanned or extended the other's point):
{agreements_block}

SPLITS (a debater rebutted the other's point; both sides' reasoning is given):
{splits_block}

Write your response in exactly this three-section format, nothing before or after it:

AGREEMENTS:
prose summary of what the models converged on, grounded only in the agreements above

SPLITS:
prose summary of where they genuinely split, with the reasoning on each side, grounded only in the splits above

OPEN QUESTION:
one question for the user to decide, phrased directly from the splits above, introducing nothing new
""".strip()

# `.*?`, not `.+?` -- see the comment on uptake.py's _TARGET_RE for why.
_AGREEMENTS_RE = re.compile(
    label("AGREEMENTS") + r"(.*?)(?=\n\s*" + label("SPLITS") + r"|\Z)", re.IGNORECASE | re.DOTALL
)
_SPLITS_RE = re.compile(
    label("SPLITS") + r"(.*?)(?=\n\s*" + label("OPEN QUESTION") + r"|\Z)", re.IGNORECASE | re.DOTALL
)
_OPEN_QUESTION_RE = re.compile(label("OPEN QUESTION") + r"(.+)\Z", re.IGNORECASE | re.DOTALL)


@dataclass(frozen=True)
class DisagreementMap:
    agreements_prose: str
    splits_prose: str
    open_question_prose: str
    skeleton: MapSkeleton


def _render_entries(entries: list[SkeletonEntry]) -> str:
    if not entries:
        return "(none)"
    return "\n\n".join(
        f"- {e.predecessor_seat} said: \"{e.predecessor_text}\"\n"
        f"  {e.seat_id} responded ({e.stance.value}, re: \"{e.target or '(no target given)'}\"): {e.text}"
        for e in entries
    )


def build_disagreement_map(
    adapter: ProviderAdapter,
    conductor: SeatConfig,
    skeleton: MapSkeleton,
) -> DisagreementMap:
    prompt = _MAP_PROMPT.format(
        agreements_block=_render_entries(skeleton.agreements),
        splits_block=_render_entries(skeleton.splits),
    )

    response = adapter.generate(
        [Message(role="user", content=prompt)],
        model=conductor.model,
        system=conductor.system_prompt,
        max_tokens=1500,
    )

    agreements_m = _AGREEMENTS_RE.search(response.text)
    splits_m = _SPLITS_RE.search(response.text)
    open_question_m = _OPEN_QUESTION_RE.search(response.text)

    return DisagreementMap(
        agreements_prose=agreements_m.group(1).strip() if agreements_m else "",
        splits_prose=splits_m.group(1).strip() if splits_m else "",
        open_question_prose=open_question_m.group(1).strip() if open_question_m else "",
        skeleton=skeleton,
    )
