from __future__ import annotations

from debate_tool.engine.reframe import parse_framings


def test_parses_multiple_framings():
    raw = (
        "FRAMING: this is really a trust problem, not a technology problem\n"
        "FRAMING: this is a distribution problem in disguise\n"
        "FRAMING: this is actually about incentive misalignment"
    )

    framings = parse_framings(raw)

    assert framings == [
        "this is really a trust problem, not a technology problem",
        "this is a distribution problem in disguise",
        "this is actually about incentive misalignment",
    ]


def test_parses_a_single_framing():
    assert parse_framings("FRAMING: just the one") == ["just the one"]


def test_no_framings_returns_empty_list():
    assert parse_framings("I don't have any alternate framings to offer.") == []


def test_blank_framing_blocks_are_dropped():
    raw = "FRAMING: real one\nFRAMING:   \nFRAMING: another real one"

    assert parse_framings(raw) == ["real one", "another real one"]
