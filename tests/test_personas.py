"""personas.py tests — config loading + prompt composition."""

import pytest

from personas import PersonaError, compose_persona_messages, load_persona, load_personas


def test_all_personas_load() -> None:
    personas = load_personas()
    assert set(personas) == {"runner", "calisthenics", "mobility", "physio"}


def test_front_matter_parsed() -> None:
    physio = load_persona("physio")
    assert physio.name == "Physiotherapy Trainer"
    assert physio.veto_level == 4
    assert "pain" in physio.signals
    assert "veto" in physio.role_prompt.lower()


def test_veto_hierarchy() -> None:
    personas = load_personas()
    assert personas["physio"].veto_level == 4
    assert personas["runner"].veto_level == 1
    assert personas["physio"].veto_level > personas["runner"].veto_level


def test_missing_persona_raises() -> None:
    with pytest.raises(PersonaError):
        load_persona("nutrition")  # 5th persona not yet added


def test_compose_includes_facts_kb_and_user(tmp_path) -> None:
    persona = load_persona("runner")
    messages = compose_persona_messages(
        persona,
        facts_block="## Current state\n- volume: 20 km",
        kb_section="- [SOURCE: pacing.md] negative split the race",
        user_message="long run tomorrow?",
    )
    assert messages[0]["role"] == "system"
    assert "Current state" in messages[0]["content"]
    assert "pacing.md" in messages[0]["content"]
    assert messages[1] == {"role": "user", "content": "long run tomorrow?"}


def test_compose_without_kb_forces_no_data(tmp_path) -> None:
    persona = load_persona("mobility")
    messages = compose_persona_messages(
        persona, facts_block="## Current state\n- volume: 20 km", kb_section="", user_message="hi"
    )
    assert "No knowledge-base match" in messages[0]["content"]
