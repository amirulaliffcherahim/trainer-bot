"""extract.py tests — mocked LLM, no network."""

import pytest

from extract import (
    ExtractionFailed,
    LogExtraction,
    ProfileExtraction,
    extract_log,
    extract_profile,
)
from llm_client import AllModelsFailed, NonRetryableError


class FakeLLMClient:
    """Scripted async responses; records every call's kwargs."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    async def chat_json_async(self, messages, **kwargs):
        self.calls.append({"messages": messages, **kwargs})
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


VALID_JSON = {
    "rpe": 6,
    "session_type": "easy_run",
    "distance_km": 5.0,
    "completed": True,
    "notes": "felt good",
}


@pytest.mark.asyncio
async def test_valid_message_extracts() -> None:
    client = FakeLLMClient([VALID_JSON])
    result = await extract_log(client, "Tuesday easy run done, 5km, felt good, RPE 6")
    assert isinstance(result, LogExtraction)
    assert result.rpe == 6
    assert result.session_type == "easy_run"
    assert result.distance_km == 5.0
    assert result.completed is True
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_malaysian_colloquial_terms_kept_in_notes() -> None:
    client = FakeLLMClient([{**VALID_JSON, "notes": "betis ketat, panas terik 34C"}])
    result = await extract_log(client, "Betis ketat, panas terik, easy 5k done")
    assert "betis" in result.notes
    assert "panas terik" in result.notes


@pytest.mark.asyncio
async def test_out_of_range_triggers_corrective_reprompt() -> None:
    client = FakeLLMClient([{"rpe": 15}, {"rpe": 8, "completed": False}])
    result = await extract_log(client, "tired")
    assert result.rpe == 8
    assert len(client.calls) == 2
    assert "invalid" in client.calls[1]["messages"][-1]["content"].lower()


@pytest.mark.asyncio
async def test_unknown_session_type_normalized_to_other() -> None:
    client = FakeLLMClient([{**VALID_JSON, "session_type": "gymstuff"}])
    result = await extract_log(client, "did some gymstuff")
    assert result.session_type == "other"


@pytest.mark.asyncio
async def test_second_failure_raises_extraction_failed() -> None:
    client = FakeLLMClient([{"rpe": 15}, {"fatigue_level": 99}])
    with pytest.raises(ExtractionFailed):
        await extract_log(client, "very tired")


@pytest.mark.asyncio
async def test_non_json_first_then_valid_recovers() -> None:
    client = FakeLLMClient([NonRetryableError("not json"), VALID_JSON])
    result = await extract_log(client, "run done")
    assert result.rpe == 6
    assert len(client.calls) == 2


@pytest.mark.asyncio
async def test_float_rpe_rounded_half_up() -> None:
    client = FakeLLMClient([{**VALID_JSON, "rpe": 6.5}])
    result = await extract_log(client, "felt like 6.5")
    assert result.rpe == 7


@pytest.mark.asyncio
async def test_string_rpe_parsed() -> None:
    client = FakeLLMClient([{**VALID_JSON, "rpe": "6"}])
    result = await extract_log(client, "RPE six")
    assert result.rpe == 6


@pytest.mark.asyncio
async def test_all_calls_use_temperature_zero() -> None:
    client = FakeLLMClient([VALID_JSON])
    await extract_log(client, "run done")
    assert all(call["temperature"] == 0.0 for call in client.calls)


@pytest.mark.asyncio
async def test_infra_errors_propagate() -> None:
    """AllModelsFailed is an infra failure — must NOT be swallowed as
    an extraction failure (caller decides on degraded mode)."""
    client = FakeLLMClient([AllModelsFailed("down")])
    with pytest.raises(AllModelsFailed):
        await extract_log(client, "run done")


# --- conversational profile intake -----------------------------------------


PROFILE_JSON = {
    "height_cm": 175,
    "weight_kg": 55.4,
    "age": 28,
    "vo2_max": None,
    "max_bpm": 190,
    "resting_bpm": 55,
    "target_race": "SELMAR Half Marathon",
    "target_time_raw": "2:30:00",
}


@pytest.mark.asyncio
async def test_extract_profile_captures_stated_fields() -> None:
    client = FakeLLMClient([PROFILE_JSON])
    profile = await extract_profile(
        client, "my height is 175, weight 55.4, max hr 190, resting 55, race SELMAR Half Marathon target 2:30:00, vo2 I don't know"
    )
    assert profile.height_cm == 175
    assert profile.weight_kg == 55.4
    assert profile.max_bpm == 190
    assert profile.vo2_max is None  # "I don't know" → omitted
    assert profile.target_race == "SELMAR Half Marathon"
    assert profile.target_time_raw == "2:30:00"
    assert profile.any_set


@pytest.mark.asyncio
async def test_extract_profile_question_captures_nothing() -> None:
    client = FakeLLMClient([{}])
    profile = await extract_profile(client, "what's my target pace?")
    assert not profile.any_set


@pytest.mark.asyncio
async def test_extract_profile_corrective_then_valid() -> None:
    client = FakeLLMClient([{"height_cm": 500}, {"height_cm": 175}])
    profile = await extract_profile(client, "height 175")
    assert profile.height_cm == 175


@pytest.mark.asyncio
async def test_extract_profile_double_failure_returns_empty() -> None:
    client = FakeLLMClient([{"age": 5}, {"weight_kg": 999}])
    profile = await extract_profile(client, "bad data")
    assert not profile.any_set  # best-effort: never raises
