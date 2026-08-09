"""Extraction — LLM pass #1: messy user text → validated structured data.

Design law: the AI proposes, Pydantic disposes.
- Pass 1: extract structured fields from the user's message.
- On ANY failure (invalid JSON, schema violation): ONE corrective re-prompt.
- Second failure → ExtractionFailed; the bot asks the user directly.

Malaysian context: colloquial terms (betis, panas terik, hujan lebat, ...)
are recognized and normalized into structured fields/notes here, so later
passes see clean data instead of raw slang.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field, ValidationError, field_validator

from llm_client import LLMClient, NonRetryableError

log = logging.getLogger(__name__)

SESSION_TYPES = frozenset(
    {
        "easy_run",
        "tempo_run",
        "interval_run",
        "long_run",
        "race",
        "strength_upper",
        "strength_legs",
        "core",
        "mobility",
        "rest",
        "other",
    }
)

EXTRACTION_SYSTEM_PROMPT = """\
You extract structured training data from a casual runner's message. The
runner writes in English or Malaysian English ("rojak").

Recognize colloquial terms and normalize them:
- "betis" = calf; "ketat"/"tight" = tightness; "kaku" = stiff; "sengal" = ache
- "panas terik"/"terik" = scorching heat; "hujan lebat" = heavy rain;
  "lembap" = humid; "angin kencang" = strong wind
- "sub-7" = pace under 7:00 min/km; "easy run"/"easy" = easy_run; "tempo" = tempo_run
- Mention of pain location (knee, quad, shin, calf...) stays in notes and is
  flagged as a symptom — never diagnose.

Rules:
- rpe: integer 1-10. Absent if the message does not state effort.
- fatigue_level: integer 1-10. Absent if not stated.
- weight_kg: 30-200. Absent if not stated.
- sleep_hours: 0-24. Absent if not stated.
- distance_km / moving_time_min: only if the message states them.
- session_type: one of: {session_types}. "other" if unclear.
- completed: true only if the session was actually done (past tense / done).
- date_raw: if the message says WHEN the activity happened (e.g. 2026-07-28,
  "yesterday", "3 days ago", "last Saturday"), copy that phrase VERBATIM;
  otherwise omit.
- notes: keep context verbatim-ish (weather, symptoms, feelings), as written.

Respond with JSON ONLY. No prose, no markdown fences.
"""

CORRECTIVE_PROMPT = """\
Your previous response was invalid. Respond again with valid JSON matching
the requested schema exactly:
- rpe / fatigue_level: integers 1-10 (omit if unknown)
- weight_kg: 30-200 (omit if unknown)
- sleep_hours: 0-24 (omit if unknown)
- distance_km: > 0 and <= 100 (omit if unknown)
- session_type: one of {session_types}
- completed: boolean
- notes: short string
Never invent values. Omit fields you are unsure about. JSON ONLY.
"""


class LogExtraction(BaseModel):
    """Validated extraction from one user message. Every field optional —
    a message may carry only part of the picture."""

    rpe: int | None = Field(default=None, ge=1, le=10)
    fatigue_level: int | None = Field(default=None, ge=1, le=10)
    weight_kg: float | None = Field(default=None, ge=30, le=200)
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    distance_km: float | None = Field(default=None, gt=0, le=100)
    moving_time_min: float | None = Field(default=None, gt=0, le=600)
    session_type: str | None = Field(default=None)
    completed: bool = False
    date_raw: str | None = Field(default=None, max_length=40)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("rpe", "fatigue_level", mode="before")
    @classmethod
    def _round_effort_to_int(cls, value: object) -> object:
        """Models sometimes emit 6.5 — round half-up to an integer RPE."""
        if value is None or isinstance(value, int):
            return value
        try:
            return int(float(value) + 0.5)
        except (TypeError, ValueError):
            raise ValueError(f"rpe/fatigue_level must be numeric, got {value!r}")

    @field_validator("session_type")
    @classmethod
    def _normalize_session(cls, value: str | None) -> str | None:
        # Lenient on labels (accuracy-critical fields are the numbers);
        # unknown labels collapse to "other" instead of burning a retry.
        if value is not None and value not in SESSION_TYPES:
            return "other"
        return value


class ExtractionFailed(RuntimeError):
    """Two extraction attempts failed — caller must ask the user directly."""


PROFILE_SYSTEM_PROMPT = """\
You extract athlete profile data from casual chat. The runner talks in
English or Malaysian English.

Capture ONLY facts the runner states about themselves:
- height_cm: number (e.g. 175)
- weight_kg: number (e.g. 55.4)
- age: integer (e.g. 28)
- vo2_max: number — ONLY if stated; "I don't know" / n/a → omit
- max_bpm: max heart rate (e.g. 190)
- resting_bpm: resting heart rate (e.g. 55)
- target_race: the race/event name (e.g. "SELMAR Half Marathon")
- target_time_raw: the goal time as stated, verbatim (e.g. "2:30:00")

Rules:
- Transcribe, never guess. Omit every field the runner does not state.
- "weighed 55.4 today" → weight_kg 55.4
- "my height is 175" → height_cm 175
- "vo2 I have no idea" → omit vo2_max
- Questions like "what's my target pace?" capture NOTHING.
- Respond with JSON ONLY, no prose, no markdown fences.
"""

_PROFILE_CORRECTIVE = (
    "Your previous response was invalid. Respond again with valid JSON: "
    "height_cm 100-250, weight_kg 30-200, age 10-100, vo2_max 20-90, "
    "max_bpm 80-250, resting_bpm 30-150, target_race string, "
    "target_time_raw 'H:MM:SS'. Omit anything not stated. JSON ONLY."
)


class ProfileExtraction(BaseModel):
    height_cm: float | None = Field(default=None, ge=100, le=250)
    weight_kg: float | None = Field(default=None, ge=30, le=200)
    age: int | None = Field(default=None, ge=10, le=100)
    vo2_max: float | None = Field(default=None, ge=20, le=90)
    max_bpm: int | None = Field(default=None, ge=80, le=250)
    resting_bpm: int | None = Field(default=None, ge=30, le=150)
    target_race: str | None = Field(default=None, max_length=120)
    target_time_raw: str | None = Field(default=None, max_length=20)

    @property
    def any_set(self) -> bool:
        return any(v is not None for v in self.model_dump().values())


async def _try_profile(
    client: LLMClient, messages: list[dict[str, str]]
) -> ProfileExtraction | None:
    try:
        raw = await client.chat_json_async(messages, temperature=0.0)
    except NonRetryableError:
        return None
    try:
        return ProfileExtraction.model_validate(raw)
    except ValidationError:
        return None


async def extract_profile(client: LLMClient, user_text: str) -> ProfileExtraction:
    """Conversational profile intake — one corrective re-prompt, then give up
    quietly (best-effort; the main pipeline continues regardless)."""
    messages = [
        {"role": "system", "content": PROFILE_SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
    ]
    parsed = await _try_profile(client, messages)
    if parsed is not None:
        return parsed
    corrective = [*messages, {"role": "user", "content": _PROFILE_CORRECTIVE}]
    parsed = await _try_profile(client, corrective)
    if parsed is not None:
        return parsed
    return ProfileExtraction()  # empty — caller treats it as a no-op


def _system_prompt() -> str:
    return EXTRACTION_SYSTEM_PROMPT.format(session_types=", ".join(sorted(SESSION_TYPES)))


def _corrective_prompt() -> str:
    return CORRECTIVE_PROMPT.format(session_types=", ".join(sorted(SESSION_TYPES)))


async def _try_extract(client: LLMClient, messages: list[dict[str, str]]) -> LogExtraction | None:
    try:
        raw = await client.chat_json_async(messages, temperature=0.0)
    except NonRetryableError as exc:
        log.warning("Extraction pass returned unparseable content: %s", exc)
        return None
    try:
        return LogExtraction.model_validate(raw)
    except ValidationError as exc:
        log.info("Extraction failed schema validation: %s", exc.errors(include_url=False)[:3])
        return None


async def extract_log(client: LLMClient, user_text: str) -> LogExtraction:
    """Extract structured data from a free-text message.

    One corrective re-prompt on failure; raises ExtractionFailed after that.
    Infra errors (AllModelsFailed, RetryableError after exhaustion) propagate
    untouched — the caller decides on degraded mode.
    """
    messages = [
        {"role": "system", "content": _system_prompt()},
        {"role": "user", "content": user_text},
    ]
    result = await _try_extract(client, messages)
    if result is not None:
        return result

    log.info("First extraction failed; issuing corrective re-prompt")
    corrective = [
        *messages,
        {"role": "user", "content": _corrective_prompt()},
    ]
    result = await _try_extract(client, corrective)
    if result is not None:
        return result

    raise ExtractionFailed(
        "Could not parse the message into structured data after two attempts."
    )
