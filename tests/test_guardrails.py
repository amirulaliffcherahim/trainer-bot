"""guardrails.py tests — red flags, volume cap, symptom signals."""

from guardrails import (
    evaluate_guardrails,
    has_symptom_signals,
    volume_increase_within_cap,
)


def test_chest_pain_triggers_cardiac_rule() -> None:
    result = evaluate_guardrails("chest pain during my run today")
    assert result.triggered
    assert result.rule_id == "cardiac"
    assert "medical" in result.response.lower()


def test_fever_triggers_rest() -> None:
    result = evaluate_guardrails("fever since yesterday, should I run?")
    assert result.triggered
    assert result.rule_id == "fever"


def test_benign_message_passes() -> None:
    result = evaluate_guardrails("tired legs but easy 5k done, RPE 6")
    assert not result.triggered
    assert result.response is None


def test_symptom_words_trigger_injury_rule() -> None:
    assert evaluate_guardrails("sharp pain in my knee").triggered
    assert evaluate_guardrails("can't weight bear after the fall").triggered


def test_volume_cap() -> None:
    assert not volume_increase_within_cap(12.0, 10.0)  # +20% → violation
    assert volume_increase_within_cap(10.8, 10.0)  # +8% → ok
    assert volume_increase_within_cap(5.0, 0.0)  # no baseline → allowed
    assert volume_increase_within_cap(9.0, 10.0)  # decrease → always ok


def test_symptom_signals() -> None:
    assert has_symptom_signals("betis ketat after long run")
    assert has_symptom_signals("quad feels tight")
    assert not has_symptom_signals("legs feel strong, great session")
