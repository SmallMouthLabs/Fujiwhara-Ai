from __future__ import annotations

from pathlib import Path

import pytest

from debate_tool.persona_config import (
    PersonaConfigError,
    load_persona,
    load_persona_set,
    load_personas,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
REAL_PERSONAS_DIR = REPO_ROOT / "config" / "personas"


def write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content)
    return path


MINIMAL = """
seat_id: test-seat
provider: anthropic
model: claude-sonnet-5
system_prompt: "You are a test seat."
"""


# --- load_persona: happy path + defaults ----------------------------------------


def test_load_persona_reads_all_fields(tmp_path):
    path = write(
        tmp_path,
        "seat.yaml",
        """
        seat_id: skeptic
        role: skeptic
        disposition: "Critical, reasoned"
        provider: anthropic
        model: claude-sonnet-5
        max_tokens: 2000
        temperature: 0.5
        system_prompt: "You are the skeptic."
        moves: ["far_analogy"]
        """,
    )

    seat = load_persona(path)

    assert seat.seat_id == "skeptic"
    assert seat.role == "skeptic"
    assert seat.disposition == "Critical, reasoned"
    assert seat.provider == "anthropic"
    assert seat.model == "claude-sonnet-5"
    assert seat.system_prompt == "You are the skeptic."
    assert seat.max_tokens == 2000
    assert seat.temperature == 0.5
    assert seat.moves == ("far_analogy",)


def test_load_persona_defaults_optional_fields(tmp_path):
    path = write(tmp_path, "seat.yaml", MINIMAL)

    seat = load_persona(path)

    assert seat.role == ""
    assert seat.disposition == ""
    assert seat.moves == ()
    assert seat.max_tokens == 1024
    assert seat.temperature is None


# --- load_persona: validation ----------------------------------------------------


def test_load_persona_missing_required_field_raises(tmp_path):
    path = write(tmp_path, "seat.yaml", "seat_id: x\nprovider: anthropic\nmodel: claude-sonnet-5\n")

    with pytest.raises(PersonaConfigError, match="system_prompt"):
        load_persona(path)


def test_load_persona_unknown_provider_raises(tmp_path):
    path = write(
        tmp_path,
        "seat.yaml",
        'seat_id: x\nprovider: gemini\nmodel: m\nsystem_prompt: "hi"\n',
    )

    with pytest.raises(PersonaConfigError, match="unknown provider"):
        load_persona(path)


def test_load_persona_unknown_role_raises(tmp_path):
    path = write(
        tmp_path,
        "seat.yaml",
        'seat_id: x\nrole: villain\nprovider: anthropic\nmodel: m\nsystem_prompt: "hi"\n',
    )

    with pytest.raises(PersonaConfigError, match="unknown role"):
        load_persona(path)


def test_load_persona_invalid_moves_type_raises(tmp_path):
    path = write(
        tmp_path,
        "seat.yaml",
        'seat_id: x\nprovider: anthropic\nmodel: m\nsystem_prompt: "hi"\nmoves: "not a list"\n',
    )

    with pytest.raises(PersonaConfigError, match="moves"):
        load_persona(path)


def test_load_persona_invalid_yaml_raises(tmp_path):
    path = write(tmp_path, "seat.yaml", "seat_id: [unclosed\n")

    with pytest.raises(PersonaConfigError, match="invalid YAML"):
        load_persona(path)


def test_load_persona_non_mapping_top_level_raises(tmp_path):
    path = write(tmp_path, "seat.yaml", "- just\n- a\n- list\n")

    with pytest.raises(PersonaConfigError, match="mapping"):
        load_persona(path)


# --- load_personas: directory ----------------------------------------------------


def test_load_personas_keys_by_seat_id(tmp_path):
    write(tmp_path, "a.yaml", 'seat_id: seat-a\nprovider: anthropic\nmodel: m\nsystem_prompt: "a"\n')
    write(tmp_path, "b.yaml", 'seat_id: seat-b\nprovider: openai\nmodel: m\nsystem_prompt: "b"\n')

    seats = load_personas(tmp_path)

    assert set(seats) == {"seat-a", "seat-b"}
    assert seats["seat-a"].provider == "anthropic"
    assert seats["seat-b"].provider == "openai"


def test_load_personas_duplicate_seat_id_raises(tmp_path):
    write(tmp_path, "a.yaml", 'seat_id: dup\nprovider: anthropic\nmodel: m\nsystem_prompt: "a"\n')
    write(tmp_path, "b.yaml", 'seat_id: dup\nprovider: openai\nmodel: m\nsystem_prompt: "b"\n')

    with pytest.raises(PersonaConfigError, match="duplicate seat_id"):
        load_personas(tmp_path)


# --- load_persona_set: role assembly ---------------------------------------------


def _role_file(seat_id: str, role: str, provider: str = "anthropic") -> str:
    return f'seat_id: {seat_id}\nrole: {role}\nprovider: {provider}\nmodel: m\nsystem_prompt: "p"\n'


def test_load_persona_set_assembles_by_role(tmp_path):
    write(tmp_path, "skeptic.yaml", _role_file("skeptic", "skeptic", "anthropic"))
    write(tmp_path, "generator.yaml", _role_file("generator", "generator", "openai"))
    write(tmp_path, "conductor.yaml", _role_file("conductor", "conductor"))
    write(tmp_path, "reframer.yaml", _role_file("reframer", "reframer"))

    result = load_persona_set(tmp_path)

    assert result.debater_skeptic.seat_id == "skeptic"
    assert result.debater_generator.seat_id == "generator"
    assert result.conductor.seat_id == "conductor"
    assert result.reframer is not None and result.reframer.seat_id == "reframer"

    kwargs = result.as_session_kwargs()
    assert kwargs["debaters"] == (result.debater_skeptic, result.debater_generator)
    assert kwargs["conductor"] is result.conductor
    assert kwargs["reframer"] is result.reframer


def test_load_persona_set_reframer_is_optional(tmp_path):
    write(tmp_path, "skeptic.yaml", _role_file("skeptic", "skeptic", "anthropic"))
    write(tmp_path, "generator.yaml", _role_file("generator", "generator", "openai"))
    write(tmp_path, "conductor.yaml", _role_file("conductor", "conductor"))

    result = load_persona_set(tmp_path)

    assert result.reframer is None
    assert result.as_session_kwargs()["reframer"] is None


def test_load_persona_set_missing_required_role_raises(tmp_path):
    write(tmp_path, "skeptic.yaml", _role_file("skeptic", "skeptic"))
    write(tmp_path, "conductor.yaml", _role_file("conductor", "conductor"))

    with pytest.raises(PersonaConfigError, match="no seat declares role 'generator'"):
        load_persona_set(tmp_path)


def test_load_persona_set_duplicate_role_raises(tmp_path):
    write(tmp_path, "skeptic1.yaml", _role_file("skeptic-1", "skeptic"))
    write(tmp_path, "skeptic2.yaml", _role_file("skeptic-2", "skeptic"))
    write(tmp_path, "generator.yaml", _role_file("generator", "generator", "openai"))
    write(tmp_path, "conductor.yaml", _role_file("conductor", "conductor"))

    with pytest.raises(PersonaConfigError, match="more than one seat declares role 'skeptic'"):
        load_persona_set(tmp_path)


def _role_file_with_model(seat_id: str, role: str, provider: str, model: str) -> str:
    return f'seat_id: {seat_id}\nrole: {role}\nprovider: {provider}\nmodel: {model}\nsystem_prompt: "p"\n'


def test_load_persona_set_rejects_both_debaters_on_same_provider_and_model(tmp_path):
    # CLAUDE.md principle 2: the two anchor debaters must be different models.
    write(tmp_path, "skeptic.yaml", _role_file_with_model("skeptic", "skeptic", "anthropic", "claude-sonnet-5"))
    write(tmp_path, "generator.yaml", _role_file_with_model("generator", "generator", "anthropic", "claude-sonnet-5"))
    write(tmp_path, "conductor.yaml", _role_file("conductor", "conductor"))

    with pytest.raises(PersonaConfigError, match="must run on different models"):
        load_persona_set(tmp_path)


def test_load_persona_set_allows_same_model_name_on_different_providers(tmp_path):
    # provider+model is what identifies the underlying model; a shared bare model
    # name across two different providers is two different models, so it's allowed.
    write(tmp_path, "skeptic.yaml", _role_file_with_model("skeptic", "skeptic", "anthropic", "m"))
    write(tmp_path, "generator.yaml", _role_file_with_model("generator", "generator", "openai", "m"))
    write(tmp_path, "conductor.yaml", _role_file("conductor", "conductor"))

    result = load_persona_set(tmp_path)

    assert result.debater_skeptic.provider == "anthropic"
    assert result.debater_generator.provider == "openai"


def test_load_persona_set_conductor_may_share_a_debaters_model(tmp_path):
    # The distinctness rule is only about the two *debaters*; the conductor (which
    # contributes no debate content) is free to reuse either debater's model.
    write(tmp_path, "skeptic.yaml", _role_file_with_model("skeptic", "skeptic", "anthropic", "claude-sonnet-5"))
    write(tmp_path, "generator.yaml", _role_file_with_model("generator", "generator", "openai", "gpt-5"))
    write(tmp_path, "conductor.yaml", _role_file_with_model("conductor", "conductor", "anthropic", "claude-sonnet-5"))

    result = load_persona_set(tmp_path)

    assert result.conductor.model == "claude-sonnet-5"


# --- the real, shipped config/personas/ directory --------------------------------


def test_the_bundled_personas_load_and_assemble():
    result = load_persona_set(REAL_PERSONAS_DIR)

    assert result.debater_skeptic.provider == "anthropic"
    assert result.debater_generator.provider == "openai"
    assert result.conductor.role == "conductor"
    assert result.reframer is not None
    # every bundled persona has a real system prompt, not an empty placeholder
    for seat in (result.debater_skeptic, result.debater_generator, result.conductor, result.reframer):
        assert len(seat.system_prompt) > 50
