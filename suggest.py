"""Suggestion engine — 10 deterministic triggers, hard anti-nag caps.

Triggers fire in CODE on computed facts (never model intuition); the AI only
writes the framing. Every suggestion carries a one-tap action.

Anti-nag hard caps (enforced here, in code):
- max 2 pushes/day, max 1 before noon
- quiet hours 22:00–07:00
- taper weeks: only phase-boundary and prediction updates push
- dismiss → the type is deduped for 7 days
- /mute (1 day / 1 week) honored
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta

from challenges import pick_template

QUIET_START_HOUR = 22
QUIET_END_HOUR = 7
MAX_PUSHES_PER_DAY = 2
MAX_BEFORE_NOON = 1
DEDUP_SECONDS = 7 * 86400

TAPER_ALLOWED_TYPES = {"phase_boundary", "prediction_update"}


@dataclass(frozen=True)
class Suggestion:
    type: str
    message: str
    action: str
    command: str


def in_quiet_hours(now: datetime) -> bool:
    return now.hour >= QUIET_START_HOUR or now.hour < QUIET_END_HOUR


class PushBudget:
    """2 pushes/day, max 1 before noon."""

    def __init__(self, max_per_day: int = MAX_PUSHES_PER_DAY, max_before_noon: int = MAX_BEFORE_NOON) -> None:
        self.max_per_day = max_per_day
        self.max_before_noon = max_before_noon
        self._day: str | None = None
        self._count = 0
        self._before_noon = 0

    def can_push(self, now: datetime) -> bool:
        day = now.date().isoformat()
        if self._day != day:
            self._day, self._count, self._before_noon = day, 0, 0
        if self._count >= self.max_per_day:
            return False
        if now.hour < 12 and self._before_noon >= self.max_before_noon:
            return False
        return True

    def record(self, now: datetime) -> None:
        self.can_push(now)  # refresh day state
        self._count += 1
        if now.hour < 12:
            self._before_noon += 1


class MuteState:
    def __init__(self) -> None:
        self._until: dict[int, float] = {}

    def mute(self, user_id: int, seconds: float) -> None:
        self._until[user_id] = time.monotonic() + seconds

    def muted(self, user_id: int, now: float | None = None) -> bool:
        until = self._until.get(user_id, 0.0)
        reference = time.monotonic() if now is None else now
        return reference < until


class DismissalDedup:
    """Dismissed suggestion types don't recur for DEDUP_SECONDS."""

    def __init__(self, ttl: float = DEDUP_SECONDS) -> None:
        self.ttl = ttl
        self._dismissed: dict[int, dict[str, float]] = {}

    def dismiss(self, user_id: int, suggestion_type: str) -> None:
        self._dismissed.setdefault(user_id, {})[suggestion_type] = time.monotonic()

    def blocked(self, user_id: int, suggestion_type: str, now: float | None = None) -> bool:
        dismissed_at = self._dismissed.get(user_id, {}).get(suggestion_type)
        if dismissed_at is None:
            return False
        elapsed = (time.monotonic() if now is None else now) - dismissed_at
        return elapsed < self.ttl


# --- triggers (each returns Suggestion | None) ----------------------------


def trigger_weekly_challenge(conn, week_start: str, phase: str) -> Suggestion | None:
    template = pick_template(conn, week_start, phase)
    if template is None:
        return None
    return Suggestion(
        type="weekly_challenge",
        message=f"This week's challenge ({template.persona}): {template.title} — "
        f"{template.description}",
        action="Accept challenge",
        command="/challenge",
    )


def trigger_prediction_update(verified_effort_count: int, pace_trend_pct: float) -> Suggestion | None:
    if verified_effort_count >= 6 and abs(pace_trend_pct) > 3.0:
        return Suggestion(
            type="prediction_update",
            message=f"{verified_effort_count} verified efforts show pace trending "
            f"{pace_trend_pct:+.1f}% — worth a fresh prediction.",
            action="See prediction",
            command="/predict",
        )
    return None


def trigger_recovery_nudge(weekly_fatigue: list[float], has_quality_session_today: bool) -> Suggestion | None:
    """Fatigue trending up 2+ weeks, or high fatigue + quality session today."""
    up = len(weekly_fatigue) >= 3 and weekly_fatigue[0] > weekly_fatigue[1] > weekly_fatigue[2]
    high_and_quality = has_quality_session_today and weekly_fatigue and weekly_fatigue[0] >= 7.0
    if up or high_and_quality:
        return Suggestion(
            type="recovery_nudge",
            message="Fatigue is trending up — today's session might be better "
            "swapped for rest or an easy day.",
            action="Swap today's run",
            command="/today",
        )
    return None


def trigger_injury_watch(symptom_counts: dict[str, int]) -> Suggestion | None:
    """Same symptom keyword in 2+ logs within 14 days."""
    flagged = {kw: count for kw, count in symptom_counts.items() if count >= 2}
    if flagged:
        keyword = max(flagged, key=flagged.get)
        return Suggestion(
            type="injury_watch",
            message=f"'{keyword}' appeared in {flagged[keyword]} logs over the last "
            "14 days — worth a physio check.",
            action="Quick check",
            command="/check",
        )
    return None


def trigger_session_adjustment(temp_c: float | None = None, rain: bool = False) -> Suggestion | None:
    if (temp_c is not None and temp_c > 31.0) or rain:
        detail = f"{temp_c}°C" if temp_c and temp_c > 31.0 else "heavy rain"
        return Suggestion(
            type="session_adjustment",
            message=f"{detail} — today's session should be scaled down (heat rules).",
            action="Adjusted plan",
            command="/today",
        )
    return None


def trigger_milestone(month_km: float, streak_days: int) -> Suggestion | None:
    if month_km >= 50.0 or streak_days >= 14:
        reason = f"{month_km:.0f} km this month" if month_km >= 50 else f"{streak_days}-day streak"
        return Suggestion(
            type="milestone",
            message=f"🎉 {reason} — that's a milestone!",
            action="Next challenge",
            command="/challenge",
        )
    return None


def trigger_plan_drift(missed_sessions: int, volume_spike_pct: float) -> Suggestion | None:
    if missed_sessions >= 2 or volume_spike_pct > 10.0:
        detail = f"{missed_sessions} sessions missed in 10 days" if missed_sessions >= 2 else f"volume spike +{volume_spike_pct:.0f}%"
        return Suggestion(
            type="plan_drift",
            message=f"{detail}. Want me to replan?",
            action="Replan",
            command="/replan",
        )
    return None


def trigger_phase_boundary(days_to_change: int) -> Suggestion | None:
    if 0 <= days_to_change <= 7:
        return Suggestion(
            type="phase_boundary",
            message=f"Phase change in {days_to_change} days — here's what's next.",
            action="Show new phase",
            command="/phase",
        )
    return None


def trigger_silence_check(days_since_last_log: int) -> Suggestion | None:
    if days_since_last_log >= 3:
        return Suggestion(
            type="silence_check",
            message=f"No logs in {days_since_last_log} days. Everything okay?",
            action="Quick log",
            command="/log",
        )
    return None


def trigger_form_check(week_of_year: int, weeks_since_injury: int | None) -> Suggestion | None:
    if week_of_year % 13 == 0 or (weeks_since_injury is not None and weeks_since_injury <= 2):
        return Suggestion(
            type="form_check",
            message="Time for a form check — send a short running/squat video?",
            action="Send video",
            command="/log",
        )
    return None


# --- orchestrator ----------------------------------------------------------


def evaluate_suggestions(
    *,
    triggers: list[Suggestion | None],
    now: datetime,
    phase_name: str | None = None,
    budget: PushBudget | None = None,
    muted: bool = False,
    dismissed_types: set[str] = frozenset(),
) -> list[Suggestion]:
    """Apply all anti-nag caps to a batch of triggered suggestions.

    Order: mute → quiet hours → taper silence → dismissal dedup → budget.
    Returns at most 2 pushable suggestions.
    """
    if muted:
        return []
    if in_quiet_hours(now):
        return []
    budget = budget or PushBudget()

    phase = (phase_name or "").lower()
    taper = "taper" in phase

    pushes: list[Suggestion] = []
    for suggestion in triggers:
        if suggestion is None:
            continue
        if taper and suggestion.type not in TAPER_ALLOWED_TYPES:
            continue
        if suggestion.type in dismissed_types:
            continue
        if not budget.can_push(now):
            break
        budget.record(now)
        pushes.append(suggestion)
    return pushes
