"""validate.py tests — citation honesty + facts-number consistency."""

from facts import FactsBlock
from validate import is_knowledge_seeking, validate_reply

FACTS = FactsBlock(
    avg_rpe_7d=6.3,
    fatigue_this_week=5.5,
    fatigue_last_week=4.5,
    volume_km_this_week=18.5,
    volume_km_last_week=17.0,
    volume_delta_pct=8.8,
    pace_avg_last3_sec_km=418.0,
    pace_avg_prev3_sec_km=425.0,
    weight_latest_kg=55.4,
    completed_sessions_7d=4,
)


def _drafts(had_kb: bool):
    if had_kb:
        return {"physio": type("D", (), {"kb_section": "- [SOURCE: triage.md] ..."})()}
    return {"physio": type("D", (), {"kb_section": ""})()}


def test_kb_used_with_citation_valid() -> None:
    result = validate_reply(
        "Rest today. [SOURCE: triage.md]", facts_block=FACTS, drafts=_drafts(True)
    )
    assert result.valid, result.problems


def test_kb_used_without_citation_rejected() -> None:
    result = validate_reply("Rest today.", facts_block=FACTS, drafts=_drafts(True))
    assert not result.valid
    assert any("SOURCE" in p for p in result.problems)


def test_no_kb_with_no_data_statement_valid() -> None:
    result = validate_reply(
        "I have no data on that topic.", facts_block=FACTS, drafts=_drafts(False)
    )
    assert result.valid, result.problems


def test_no_kb_without_no_data_rejected() -> None:
    result = validate_reply(
        "Rest today.", facts_block=FACTS, drafts=_drafts(False), knowledge_seeking=True
    )
    assert not result.valid
    assert any("no data" in p for p in result.problems)


def test_no_kb_ok_for_routine_log() -> None:
    """Routine messages ('easy 5k done') are not forced to say 'no data'."""
    result = validate_reply(
        "Nice easy 5k! Legs feeling fresh.",
        facts_block=FACTS,
        drafts=_drafts(False),
        knowledge_seeking=False,
    )
    assert result.valid, result.problems


def test_is_knowledge_seeking() -> None:
    assert is_knowledge_seeking("why do I need a taper?")
    assert is_knowledge_seeking("what pace should I run")
    assert is_knowledge_seeking("kenapa kena rest")
    assert not is_knowledge_seeking("easy 5k done, RPE 6")
    assert not is_knowledge_seeking("weighed 55.4 today")


def test_exact_fact_number_valid() -> None:
    result = validate_reply(
        "This week is 18.5 km. [SOURCE: pacing.md]",
        facts_block=FACTS,
        drafts=_drafts(True),
    )
    assert result.valid, result.problems


def test_near_miss_number_rejected() -> None:
    result = validate_reply(
        "This week is 18.0 km. [SOURCE: pacing.md]",
        facts_block=FACTS,
        drafts=_drafts(True),
    )
    assert not result.valid
    assert any("18.0" in p for p in result.problems)


def test_unrelated_numbers_not_flagged() -> None:
    result = validate_reply(
        "Plan 5 km tomorrow, easy. [SOURCE: pacing.md]",
        facts_block=FACTS,
        drafts=_drafts(True),
    )
    assert result.valid, result.problems


def test_empty_reply_rejected() -> None:
    result = validate_reply("", facts_block=FACTS, drafts=_drafts(False))
    assert not result.valid


def test_too_short_reply_rejected() -> None:
    result = validate_reply("ok", facts_block=FACTS, drafts=_drafts(False))
    assert not result.valid
