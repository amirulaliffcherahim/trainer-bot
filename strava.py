"""Strava screenshot pipeline — the accuracy-critical path.

screenshot + caption →
  1. read pass: OCR text → DeepSeek parses RAW displayed fields
  2. math check (code): pace_computed = time / distance vs pace read
     → >5 s/km discrepancy flags the field UNCERTAIN
  3. plausibility (code): sane ranges
  4. plan comparison: vs workout_plan for that date → deltas
  5. echo-confirm: bot echoes the numbers back; user confirms or corrects
  6. verified=1 storage — unverified numbers NEVER enter stats

Design law: the AI reads, the code computes. avg_pace is recomputed in code;
the model's read of the displayed pace is only cross-checked against it.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field

from pydantic import BaseModel, Field, ValidationError

from db import save_log
from llm_client import LLMClient, NonRetryableError

log = logging.getLogger(__name__)

PACE_TOLERANCE_SEC_KM = 5.0  # >5 s/km discrepancy → UNCERTAIN

_PARSE_SYSTEM_PROMPT = """\
You transcribe a running-app screenshot (Strava/Garmin style) from OCR text.

Extract the RAW displayed values exactly as shown:
- activity_type: run / ride / walk / other
- distance_km: number
- moving_time_min: total moving time in minutes (e.g. 72.6)
- avg_pace_text: the displayed average pace as m:ss (e.g. "6:58")
- elevation_m: number (omit if not shown)
- avg_hr: number (omit if not shown)
- date: YYYY-MM-DD if visible, else omit

Rules:
- Transcribe, never compute. If the pace column shows 6:10, write "6:10" —
  do NOT derive it from distance and time.
- Omit fields that are absent or unreadable.
- Respond with JSON ONLY, no prose, no markdown fences.
"""

_CORRECTIVE = """\
Your previous response was invalid. Respond again with valid JSON:
- distance_km: number > 0
- moving_time_min: number > 0
- avg_pace_text: "m:ss" exactly as displayed
- avg_hr: number 30-220 (omit if not shown)
- date: YYYY-MM-DD (omit if not visible)
Transcribe only. JSON ONLY.
"""


class StravaFields(BaseModel):
    activity_type: str | None = None
    distance_km: float | None = Field(default=None, gt=0, le=100)
    moving_time_min: float | None = Field(default=None, gt=0, le=600)
    avg_pace_text: str | None = None
    elevation_m: float | None = Field(default=None, ge=0, le=10000)
    avg_hr: float | None = Field(default=None, ge=30, le=220)
    date: str | None = None

    @property
    def pace_sec_km(self) -> float | None:
        """The displayed pace parsed to sec/km (code-side, for cross-check)."""
        if not self.avg_pace_text:
            return None
        match = re.search(r"(\d{1,2}):(\d{2})", self.avg_pace_text.strip())
        if not match:
            return None
        return int(match.group(1)) * 60 + int(match.group(2))


class ParseFailed(RuntimeError):
    """Two parse attempts failed — bot asks the user to type the numbers."""


async def _try_parse(client: LLMClient, messages: list[dict[str, str]]) -> StravaFields | None:
    try:
        raw = await client.chat_json_async(messages, temperature=0.0)
    except NonRetryableError:
        return None
    try:
        return StravaFields.model_validate(raw)
    except ValidationError:
        return None


async def parse_screenshot(client: LLMClient, ocr_text: str) -> StravaFields:
    """OCR text → validated raw fields. One corrective re-prompt, then fail."""
    messages = [
        {"role": "system", "content": _PARSE_SYSTEM_PROMPT},
        {"role": "user", "content": ocr_text},
    ]
    parsed = await _try_parse(client, messages)
    if parsed is not None:
        return parsed
    corrective = [*messages, {"role": "user", "content": _CORRECTIVE}]
    parsed = await _try_parse(client, corrective)
    if parsed is not None:
        return parsed
    raise ParseFailed("could not read the screenshot after two attempts")


def math_check(fields: StravaFields) -> tuple[float | None, float | None, list[str]]:
    """(computed_pace_sec_km, delta_vs_read_sec_km, uncertain_flags).

    pace is COMPUTED in code from distance/time. The model's read of the
    displayed pace is trusted only if it agrees with the math within
    PACE_TOLERANCE_SEC_KM.
    """
    computed = None
    if fields.distance_km and fields.moving_time_min:
        computed = fields.moving_time_min * 60.0 / fields.distance_km
    delta = None
    uncertain: list[str] = []
    read_pace = fields.pace_sec_km
    if computed is not None and read_pace is not None:
        delta = computed - read_pace
        if abs(delta) > PACE_TOLERANCE_SEC_KM:
            uncertain.append("avg_pace")
    return computed, delta, uncertain


def plausibility_check(fields: StravaFields) -> list[str]:
    problems: list[str] = []
    if fields.distance_km is not None and not (0.1 <= fields.distance_km <= 50):
        problems.append(f"distance {fields.distance_km} km outside 0.1–50")
    if fields.moving_time_min is not None and not (1 <= fields.moving_time_min <= 600):
        problems.append(f"moving time {fields.moving_time_min} min outside 1–600")
    if fields.avg_hr is not None and not (30 <= fields.avg_hr <= 220):
        problems.append(f"HR {fields.avg_hr} outside 30–220")
    if fields.elevation_m is not None and not (0 <= fields.elevation_m <= 10000):
        problems.append(f"elevation {fields.elevation_m} m outside 0–10000")
    return problems


@dataclass
class StravaRead:
    """One processed screenshot, pending user confirmation."""

    fields: StravaFields
    ocr_text: str
    uncertain: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    computed_pace_sec_km: float | None = None
    pace_delta_sec_km: float | None = None
    plan: dict | None = None
    plan_deltas: dict | None = None

    @property
    def verified(self) -> bool:
        return False


def find_plan(conn, date_iso: str | None) -> dict | None:
    if not date_iso:
        return None
    row = conn.execute(
        "SELECT * FROM workout_plan WHERE date = ? LIMIT 1", (date_iso,)
    ).fetchone()
    return dict(row) if row else None


def plan_deltas(read: StravaRead) -> dict | None:
    """Deterministic comparison of the read against the prescribed session."""
    plan = read.plan
    if not plan:
        return None
    deltas: dict = {}
    prescribed = plan.get("prescribed_km")
    if read.fields.distance_km is not None and prescribed:
        deltas["distance_km"] = round(read.fields.distance_km - float(prescribed), 2)
    from workouts import parse_pace_sec_km

    target = parse_pace_sec_km(plan.get("target_pace"))
    if read.computed_pace_sec_km is not None and target:
        deltas["pace_sec_km"] = round(read.computed_pace_sec_km - target, 1)
    return deltas or None


def format_pace(sec_km: float | None) -> str:
    if sec_km is None:
        return "n/a"
    total = int(round(sec_km))
    return f"{total // 60}:{total % 60:02d}/km"


def build_echo(read: StravaRead) -> str:
    """The echo-confirm message — every number the bot will store, shown back."""
    fields = read.fields
    lines = [
        "Read from screenshot:",
        f"- Distance: {fields.distance_km if fields.distance_km is not None else '?'} km",
        f"- Moving time: {fields.moving_time_min if fields.moving_time_min is not None else '?'} min",
        f"- Pace (computed in code): {format_pace(read.computed_pace_sec_km)}",
    ]
    if fields.pace_sec_km is not None:
        lines.append(f"- Pace (as displayed): {format_pace(fields.pace_sec_km)}")
    if "avg_pace" in read.uncertain:
        lines.append(
            f"⚠️ UNCERTAIN: displayed pace ({format_pace(fields.pace_sec_km)}) "
            f"doesn't match distance/time ({format_pace(read.computed_pace_sec_km)})"
        )
    if read.plan:
        planned = (
            f"{read.plan.get('prescribed_km')} km @ {read.plan.get('target_pace')}"
            if read.plan.get("prescribed_km")
            else read.plan.get("target_pace")
        )
        lines.append(f"- Planned: {read.plan.get('session_type')} ({planned})")
        if read.plan_deltas:
            if "distance_km" in read.plan_deltas:
                lines.append(f"- Distance vs plan: {read.plan_deltas['distance_km']:+.2f} km")
            if "pace_sec_km" in read.plan_deltas:
                lines.append(f"- Pace vs target: {read.plan_deltas['pace_sec_km']:+.1f} s/km")
    for problem in read.problems:
        lines.append(f"⚠️ {problem}")
    lines.append("Everything correct?")
    return "\n".join(lines)


def build_confirm_keyboard(draft_id: str):
    """Echo-confirm buttons. callback_data stays well under Telegram's
    64-byte limit — payloads are short draft refs, never data."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    buttons = [
        [
            InlineKeyboardButton("✅ Correct", callback_data=f"cf:{draft_id}"),
            InlineKeyboardButton("Fix distance", callback_data=f"cffix:{draft_id}:distance_km"),
        ],
        [
            InlineKeyboardButton("Fix pace", callback_data=f"cffix:{draft_id}:avg_pace"),
            InlineKeyboardButton("Fix date", callback_data=f"cffix:{draft_id}:date"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


async def process_screenshot(
    client: LLMClient,
    conn,
    ocr_text: str,
    *,
    caption: str = "",
) -> StravaRead:
    """Full read pass: parse → math check → plausibility → plan comparison."""
    fields = await parse_screenshot(client, ocr_text)
    computed, delta, uncertain = math_check(fields)
    problems = plausibility_check(fields)
    read = StravaRead(
        fields=fields,
        ocr_text=ocr_text,
        uncertain=uncertain,
        problems=problems,
        computed_pace_sec_km=computed,
        pace_delta_sec_km=delta,
    )
    read.plan = find_plan(conn, fields.date)
    read.plan_deltas = plan_deltas(read)
    return read


def confirm_draft(conn, read: StravaRead, *, user_id: int, caption: str = "") -> int:
    """User confirmed — store as verified=1. Returns the log id."""
    fields = read.fields
    log_id = save_log(
        conn,
        date=fields.date or time.strftime("%Y-%m-%d"),
        user_id=user_id,
        user_input=caption or read.ocr_text[:500],
        ai_response=build_echo(read),
        session_type=fields.activity_type or "run",
        distance_km=fields.distance_km,
        moving_time_min=fields.moving_time_min,
        completed=1,
        verified=1,
        model_used=None,
        prompt_version="strava-v1",
        raw_payload=read.ocr_text[:2000],
    )
    # Verified efforts feed the prediction engine's anchors (best-effort
    # selection + exponent refit). Code-computed values only.
    if fields.distance_km and fields.moving_time_min:
        conn.execute(
            "INSERT INTO performance_anchors (date, distance_km, time_sec, source, verified) "
            "VALUES (?, ?, ?, 'screenshot', 1)",
            (
                fields.date or time.strftime("%Y-%m-%d"),
                fields.distance_km,
                int(round(fields.moving_time_min * 60)),
            ),
        )
        conn.commit()
    return log_id
