from __future__ import annotations

from debate_tool.engine.turns import Stance
from debate_tool.engine.uptake import parse_uptake


def test_parses_well_formed_response():
    raw = (
        "TARGET: the claim that X causes Y\n"
        "STANCE: rebut\n"
        "ARGUMENT: because Z is a confound that better explains the correlation."
    )

    result = parse_uptake(raw)

    assert result.ok is True
    assert result.target == "the claim that X causes Y"
    assert result.stance is Stance.REBUT
    assert result.argument == "because Z is a confound that better explains the correlation."


def test_tolerates_markdown_bold_labels():
    raw = "**TARGET:** the point\n**STANCE:** extend\n**ARGUMENT:** more reasoning"

    result = parse_uptake(raw)

    assert result.ok is True
    assert result.target == "the point"
    assert result.stance is Stance.EXTEND


def test_tolerates_bold_label_without_trailing_asterisks_on_colon():
    # the "**LABEL**:" bold style, as opposed to "**LABEL:**"
    raw = "**TARGET**: the point\n**STANCE**: rebut\n**ARGUMENT**: because reasons"

    result = parse_uptake(raw)

    assert result.ok is True
    assert result.target == "the point"
    assert result.stance is Stance.REBUT
    assert result.argument == "because reasons"


def test_asterisks_inside_content_are_preserved_not_stripped():
    # Regression for the bold-label tolerance once being a global strip of every
    # asterisk, which silently deleted emphasis, math, and markers from content.
    raw = (
        "TARGET: the claim that revenue scales as price * volume\n"
        "STANCE: rebut\n"
        "ARGUMENT: no, margin **compresses** past the inflection, so 2 * price does not mean 2 * profit"
    )

    result = parse_uptake(raw)

    assert result.ok is True
    assert result.target == "the claim that revenue scales as price * volume"
    assert result.argument == (
        "no, margin **compresses** past the inflection, so 2 * price does not mean 2 * profit"
    )


def test_bold_label_with_bolded_content_keeps_content_asterisks():
    raw = "**TARGET:** point\n**STANCE:** extend\n**ARGUMENT:** I fully endorse **this** part"

    result = parse_uptake(raw)

    assert result.ok is True
    assert result.argument == "I fully endorse **this** part"


def test_missing_field_is_not_ok():
    raw = "STANCE: steelman\nARGUMENT: some reasoning, no target given"

    result = parse_uptake(raw)

    assert result.ok is False
    assert result.target is None
    assert result.stance is Stance.STEELMAN


def test_invalid_stance_word_is_not_recognized():
    raw = "TARGET: the point\nSTANCE: agree\nARGUMENT: reasoning"

    result = parse_uptake(raw)

    assert result.ok is False
    assert result.stance is None


def test_free_text_with_no_labels_is_not_ok():
    result = parse_uptake("I think the other debater has a point about scalability.")

    assert result.ok is False
    assert result.target is None
    assert result.stance is None
    assert result.argument is None


def test_argument_field_captures_everything_to_the_end_including_newlines():
    raw = "TARGET: t\nSTANCE: extend\nARGUMENT: line one\nline two\nline three"

    result = parse_uptake(raw)

    assert result.argument == "line one\nline two\nline three"
