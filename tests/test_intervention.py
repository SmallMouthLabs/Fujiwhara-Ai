from __future__ import annotations

from pathlib import Path

import pytest

from debate_tool.intervention.hooks import Hook
from debate_tool.intervention.moves import Move, MoveContext, MoveRenderError
from debate_tool.intervention.policy import (
    InterventionPolicy,
    PolicyConfigError,
    load_moves,
    load_policy,
)


def write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content)
    return path


# --- Move / MoveContext ----------------------------------------------------------


def test_move_renders_template_against_context():
    move = Move(name="far_analogy", when_to_use="ideas feel obvious", template="Seed: {seed}. Seat: {seat_id}.")
    context = MoveContext(seed="a smart fridge", seat_id="generator")

    assert move.render(context) == "Seed: a smart fridge. Seat: generator."


def test_move_can_use_recent_targets():
    move = Move(name="m", when_to_use="x", template="Already raised: {recent_targets}")
    context = MoveContext(seed="s", seat_id="g", recent_targets=("point one", "point two"))

    assert move.render(context) == "Already raised: point one, point two"


def test_move_render_raises_on_unknown_placeholder():
    move = Move(name="m", when_to_use="x", template="Uses {nonexistent_field}")
    context = MoveContext(seed="s", seat_id="g")

    with pytest.raises(MoveRenderError, match="nonexistent_field"):
        move.render(context)


# --- load_moves --------------------------------------------------------------------


def test_load_moves_on_empty_directory_returns_empty_dict(tmp_path):
    assert load_moves(tmp_path) == {}


def test_load_moves_on_nonexistent_directory_returns_empty_dict(tmp_path):
    assert load_moves(tmp_path / "does-not-exist") == {}


def test_load_moves_reads_a_valid_move_file(tmp_path):
    write(
        tmp_path,
        "far_analogy.yaml",
        """
        name: far_analogy
        when_to_use: "ideas feel obvious"
        template: "What else works like {seed}?"
        """,
    )

    moves = load_moves(tmp_path)

    assert set(moves) == {"far_analogy"}
    assert moves["far_analogy"].when_to_use == "ideas feel obvious"
    assert moves["far_analogy"].template == "What else works like {seed}?"


def test_load_moves_missing_field_raises(tmp_path):
    write(tmp_path, "bad.yaml", 'name: m\ntemplate: "t"\n')  # missing when_to_use

    with pytest.raises(PolicyConfigError, match="when_to_use"):
        load_moves(tmp_path)


def test_load_moves_duplicate_name_raises(tmp_path):
    write(tmp_path, "a.yaml", 'name: dup\nwhen_to_use: "x"\ntemplate: "t1"\n')
    write(tmp_path, "b.yaml", 'name: dup\nwhen_to_use: "x"\ntemplate: "t2"\n')

    with pytest.raises(PolicyConfigError, match="duplicate move name"):
        load_moves(tmp_path)


def test_load_moves_invalid_yaml_raises(tmp_path):
    write(tmp_path, "bad.yaml", "name: [unclosed\n")

    with pytest.raises(PolicyConfigError, match="invalid YAML"):
        load_moves(tmp_path)


# --- load_policy --------------------------------------------------------------------


def test_load_policy_empty_file_yields_empty_mapping(tmp_path):
    path = write(tmp_path, "policy.yaml", "hooks: {}\n")

    policy = load_policy(path, moves={})

    assert policy.resolve(Hook.ON_PHASE_CHANGE) == []


def test_load_policy_maps_a_hook_to_a_registered_move(tmp_path):
    path = write(tmp_path, "policy.yaml", "hooks:\n  on_phase_change: [far_analogy]\n")
    moves = {"far_analogy": Move(name="far_analogy", when_to_use="x", template="t")}

    policy = load_policy(path, moves=moves)

    resolved = policy.resolve(Hook.ON_PHASE_CHANGE)
    assert [m.name for m in resolved] == ["far_analogy"]
    assert policy.resolve(Hook.ON_USER_STALL) == []


def test_load_policy_unknown_hook_raises(tmp_path):
    path = write(tmp_path, "policy.yaml", "hooks:\n  on_typo: []\n")

    with pytest.raises(PolicyConfigError, match="unknown hook"):
        load_policy(path, moves={})


def test_load_policy_unregistered_move_raises(tmp_path):
    path = write(tmp_path, "policy.yaml", "hooks:\n  on_phase_change: [nonexistent_move]\n")

    with pytest.raises(PolicyConfigError, match="unregistered move"):
        load_policy(path, moves={})


def test_load_policy_malformed_hooks_shape_raises(tmp_path):
    path = write(tmp_path, "policy.yaml", "hooks:\n  on_phase_change: not-a-list\n")

    with pytest.raises(PolicyConfigError, match="list of move names"):
        load_policy(path, moves={})


# --- InterventionPolicy.fire ---------------------------------------------------------


def test_fire_with_no_moves_mapped_returns_an_event_with_nothing_applied():
    policy = InterventionPolicy(moves={}, mapping={})

    event = policy.fire(Hook.ON_EARLY_NARROWING, MoveContext(seed="s", seat_id=""), round_index=2)

    assert event.hook is Hook.ON_EARLY_NARROWING
    assert event.round_index == 2
    assert event.applied_moves == ()
    assert event.rendered == ()


def test_fire_renders_every_mapped_move_in_order():
    move_a = Move(name="a", when_to_use="x", template="A saw: {seed}")
    move_b = Move(name="b", when_to_use="x", template="B saw: {seed}")
    policy = InterventionPolicy(
        moves={"a": move_a, "b": move_b}, mapping={Hook.ON_PHASE_CHANGE: ("a", "b")}
    )

    event = policy.fire(Hook.ON_PHASE_CHANGE, MoveContext(seed="the seed", seat_id=""), round_index=3)

    assert event.applied_moves == ("a", "b")
    assert event.rendered == ("A saw: the seed", "B saw: the seed")
