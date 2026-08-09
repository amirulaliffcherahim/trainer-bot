"""test_strava.py — screenshot pipeline: parse, math check, plausibility,
plan comparison, echo-confirm storage, image cap (no network)."""

import io

import pytest
from PIL import Image

import strava
from db import init_db, save_log
from llm_client import NonRetryableError
from ocr import MAX_DIM, cap_image
from strava import (
    ParseFailed,
    StravaFields,
    StravaRead,
    build_confirm_keyboard,
    confirm_draft,
    math_check,
    parse_screenshot,
    plan_deltas,
    plausibility_check,
    process_screenshot,
)


class FakeLLMClient:
    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    async def chat_json_async(self, messages, **kwargs):
        self.calls.append(kwargs)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


OCR_TEXT = """Saturday Long Run
10.42 km
72:38
6:58 /km
124 bpm
Avg HR
102 m
Elev Gain
"""

FIELDS_JSON = {
    "activity_type": "run",
    "distance_km": 10.42,
    "moving_time_min": 72.6,
    "avg_pace_text": "6:58",
    "elevation_m": 102.0,
    "avg_hr": 124.0,
    "date": "2026-07-11",
}


@pytest.mark.asyncio
async def test_parse_screenshot_extracts_fields() -> None:
    client = FakeLLMClient([FIELDS_JSON])
    fields = await parse_screenshot(client, OCR_TEXT)
    assert fields.distance_km == 10.42
    assert fields.moving_time_min == 72.6
    assert fields.pace_sec_km == 418  # "6:58" parsed in code
    assert fields.date == "2026-07-11"
    assert client.calls[0]["temperature"] == 0.0


@pytest.mark.asyncio
async def test_parse_corrective_reprompt_then_success() -> None:
    client = FakeLLMClient([{"distance_km": 0}, FIELDS_JSON])  # distance 0 invalid
    fields = await parse_screenshot(client, OCR_TEXT)
    assert fields.distance_km == 10.42
    assert len(client.calls) == 2


@pytest.mark.asyncio
async def test_parse_double_failure_raises() -> None:
    client = FakeLLMClient([{"distance_km": 0}, {"moving_time_min": -5}])
    with pytest.raises(ParseFailed):
        await parse_screenshot(client, OCR_TEXT)


@pytest.mark.asyncio
async def test_parse_non_json_then_valid() -> None:
    client = FakeLLMClient([NonRetryableError("not json"), FIELDS_JSON])
    fields = await parse_screenshot(client, OCR_TEXT)
    assert fields.distance_km == 10.42


def test_math_check_consistent() -> None:
    fields = StravaFields(**FIELDS_JSON)
    computed, delta, uncertain = math_check(fields)
    assert computed == pytest.approx(418.04, abs=0.1)  # 72.6*60/10.42
    assert abs(delta) < 1
    assert uncertain == []


def test_math_check_doctored_pace_flagged_uncertain() -> None:
    """Displayed pace contradicts distance/time → UNCERTAIN."""
    fields = StravaFields(**{**FIELDS_JSON, "avg_pace_text": "6:10"})
    computed, delta, uncertain = math_check(fields)
    assert delta == pytest.approx(48.0, abs=1.0)
    assert uncertain == ["avg_pace"]


def test_math_check_missing_time_no_flag() -> None:
    fields = StravaFields(distance_km=10.42)
    computed, delta, uncertain = math_check(fields)
    assert computed is None
    assert uncertain == []


def test_plausibility_check() -> None:
    assert plausibility_check(StravaFields(**FIELDS_JSON)) == []
    # model_construct bypasses validation — simulates a raw/legacy value the
    # plausibility layer must still catch.
    assert plausibility_check(StravaFields.model_construct(avg_hr=250.0))
    # 60 km passes the model (le=100) but plausibility caps at 50.
    assert plausibility_check(StravaFields(distance_km=60.0, moving_time_min=5.0))


def test_plan_comparison_deltas() -> None:
    conn = init_db(":memory:")
    conn.execute(
        "INSERT INTO workout_plan (date, session_type, prescribed_km, target_pace) "
        "VALUES ('2026-07-11', 'long_run', 10.0, '7:10 min/km')"
    )
    conn.commit()
    read = StravaRead(
        fields=StravaFields(**FIELDS_JSON),
        ocr_text=OCR_TEXT,
        computed_pace_sec_km=418.0,
    )
    read.plan = strava.find_plan(conn, "2026-07-11")
    read.plan_deltas = plan_deltas(read)
    assert read.plan_deltas["distance_km"] == pytest.approx(0.42)
    assert read.plan_deltas["pace_sec_km"] == pytest.approx(-12.0)  # 6:58 vs 7:10


@pytest.mark.asyncio
async def test_process_screenshot_assembles_read() -> None:
    conn = init_db(":memory:")
    client = FakeLLMClient([FIELDS_JSON])
    read = await process_screenshot(client, conn, OCR_TEXT, caption="Saturday long run done")
    assert read.fields.distance_km == 10.42
    assert read.computed_pace_sec_km is not None
    assert read.uncertain == []
    assert read.plan is None  # no plan seeded for that date


def test_echo_contains_numbers_and_uncertainty() -> None:
    read = StravaRead(
        fields=StravaFields(**FIELDS_JSON),
        ocr_text=OCR_TEXT,
        computed_pace_sec_km=418.0,
        uncertain=["avg_pace"],
    )
    echo = strava.build_echo(read)
    assert "10.42" in echo
    assert "6:58" in echo
    assert "UNCERTAIN" in echo


def test_confirm_draft_stores_verified() -> None:
    conn = init_db(":memory:")
    read = StravaRead(
        fields=StravaFields(**FIELDS_JSON),
        ocr_text=OCR_TEXT,
        computed_pace_sec_km=418.0,
    )
    log_id = confirm_draft(conn, read, user_id=1, caption="Saturday long run done")
    row = conn.execute("SELECT * FROM daily_logs WHERE id = ?", (log_id,)).fetchone()
    assert row["verified"] == 1
    assert row["distance_km"] == 10.42
    assert row["avg_pace_sec_km"] == 418  # computed in code, never from the model
    assert row["completed"] == 1
    # Verified efforts become prediction anchors (code-computed values only).
    anchor = conn.execute(
        "SELECT * FROM performance_anchors WHERE source = 'screenshot'"
    ).fetchone()
    assert anchor is not None
    assert anchor["distance_km"] == 10.42
    assert anchor["time_sec"] == 4356  # 72.6 min
    assert anchor["verified"] == 1


def test_confirm_draft_corrected_pace_used() -> None:
    conn = init_db(":memory:")
    fields = StravaFields(**{**FIELDS_JSON, "avg_pace_text": "6:10"})
    read = StravaRead(fields=fields, ocr_text=OCR_TEXT)
    computed, _, _ = math_check(fields)
    read.computed_pace_sec_km = computed
    log_id = confirm_draft(conn, read, user_id=1)
    row = conn.execute("SELECT * FROM daily_logs WHERE id = ?", (log_id,)).fetchone()
    assert row["avg_pace_sec_km"] == 418  # code-computed, NOT the doctored 6:10


def test_cap_image_resizes_large() -> None:
    img = Image.new("RGB", (8000, 2000), "white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    capped = cap_image(buf.getvalue())
    capped_img = Image.open(io.BytesIO(capped))
    assert max(capped_img.size) <= MAX_DIM
    assert capped_img.size == (4096, 1024)  # aspect preserved


def test_cap_image_keeps_small() -> None:
    img = Image.new("RGB", (800, 600), "white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    capped = Image.open(io.BytesIO(cap_image(buf.getvalue())))
    assert capped.size == (800, 600)
