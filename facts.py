"""Computed facts — deterministic numbers derived from stored logs.

Design law #2: the AI talks, the code does math. Everything in this module is
pure and deterministic; persona prompts receive the formatted block and must
never recompute numbers themselves. KL/Selangor heat and humidity enter via
extracted notes (weather) — personas interpret them, code only reports the
raw trends.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class FactsBlock:
    avg_rpe_7d: float | None
    fatigue_this_week: float | None
    fatigue_last_week: float | None
    volume_km_this_week: float
    volume_km_last_week: float
    volume_delta_pct: float | None
    pace_avg_last3_sec_km: float | None
    pace_avg_prev3_sec_km: float | None
    weight_latest_kg: float | None
    completed_sessions_7d: int


def _mean(values: list[float]) -> float | None:
    return round(statistics.fmean(values), 1) if values else None


def _iso_week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def compute_facts(logs: list[dict], *, today: date) -> FactsBlock:
    """Compute the facts block from daily_log rows (most recent last).

    Pure function: takes rows, returns numbers. Tests feed synthetic rows;
    the bot feeds get_recent_history() output.
    """
    if not logs:
        return FactsBlock(
            avg_rpe_7d=None,
            fatigue_this_week=None,
            fatigue_last_week=None,
            volume_km_this_week=0.0,
            volume_km_last_week=0.0,
            volume_delta_pct=None,
            pace_avg_last3_sec_km=None,
            pace_avg_prev3_sec_km=None,
            weight_latest_kg=None,
            completed_sessions_7d=0,
        )

    week_start = _iso_week_start(today)
    last_week_start = week_start - timedelta(days=7)
    window_start = today - timedelta(days=6)

    rpe_7d: list[float] = []
    completed_7d = 0
    fatigue_this: list[float] = []
    fatigue_last: list[float] = []
    volume_this = 0.0
    volume_last = 0.0
    pace_verified: list[tuple[str, float]] = []
    weight_entries: list[tuple[str, float]] = []

    for row in logs:
        log_date = row.get("date")
        completed = bool(row.get("completed", 0))
        verified = bool(row.get("verified", 0))

        if row.get("rpe") is not None and log_date >= window_start.isoformat():
            rpe_7d.append(float(row["rpe"]))
        if completed and log_date >= window_start.isoformat():
            completed_7d += 1

        fatigue = row.get("fatigue_level")
        if fatigue is not None:
            if log_date >= week_start.isoformat():
                fatigue_this.append(float(fatigue))
            elif log_date >= last_week_start.isoformat():
                fatigue_last.append(float(fatigue))

        distance = row.get("distance_km")
        if distance is not None and completed:
            if log_date >= week_start.isoformat():
                volume_this += float(distance)
            elif log_date >= last_week_start.isoformat():
                volume_last += float(distance)

        if verified and row.get("avg_pace_sec_km") is not None:
            pace_verified.append((log_date, float(row["avg_pace_sec_km"])))

        if row.get("weight_kg") is not None:
            weight_entries.append((log_date, float(row["weight_kg"])))

    pace_verified.sort(key=lambda pair: pair[0])
    pace_last3 = [p for _, p in pace_verified[-3:]]
    pace_prev3 = [p for _, p in pace_verified[-6:-3]]

    volume_delta_pct = None
    if volume_last > 0:
        volume_delta_pct = round((volume_this - volume_last) / volume_last * 100, 1)

    weight_latest = weight_entries[-1][1] if weight_entries else None

    return FactsBlock(
        avg_rpe_7d=_mean(rpe_7d),
        fatigue_this_week=_mean(fatigue_this),
        fatigue_last_week=_mean(fatigue_last),
        volume_km_this_week=round(volume_this, 2),
        volume_km_last_week=round(volume_last, 2),
        volume_delta_pct=volume_delta_pct,
        pace_avg_last3_sec_km=round(statistics.fmean(pace_last3), 1) if pace_last3 else None,
        pace_avg_prev3_sec_km=round(statistics.fmean(pace_prev3), 1) if pace_prev3 else None,
        weight_latest_kg=weight_latest,
        completed_sessions_7d=completed_7d,
    )


def _format_pace(sec_km: float | None) -> str:
    if sec_km is None:
        return "n/a"
    total = int(round(sec_km))
    return f"{total // 60}:{total % 60:02d}/km"


def format_facts_block(facts: FactsBlock) -> str:
    """Render the facts block injected into every persona prompt.

    Personas must treat these numbers as ground truth and never recompute.
    """
    fatigue = "n/a"
    if facts.fatigue_this_week is not None:
        fatigue = f"{facts.fatigue_this_week}"
        if facts.fatigue_last_week is not None:
            delta = facts.fatigue_this_week - facts.fatigue_last_week
            fatigue += f" vs last week {facts.fatigue_last_week} ({delta:+.1f})"

    volume = f"{facts.volume_km_this_week} km"
    if facts.volume_delta_pct is not None:
        volume += f" vs last week {facts.volume_km_last_week} km ({facts.volume_delta_pct:+.1f}%)"

    pace = "n/a"
    if facts.pace_avg_last3_sec_km is not None:
        pace = _format_pace(facts.pace_avg_last3_sec_km)
        if facts.pace_avg_prev3_sec_km is not None:
            pace += f" vs previous 3 {_format_pace(facts.pace_avg_prev3_sec_km)}"

    return (
        "## Current state (computed from the athlete's logs — these numbers "
        "are facts, do not recompute or second-guess them)\n"
        f"- 7-day average RPE: {facts.avg_rpe_7d if facts.avg_rpe_7d is not None else 'n/a'}\n"
        f"- Fatigue trend: {fatigue}\n"
        f"- Weekly volume: {volume}\n"
        f"- Pace trend (verified runs): {pace}\n"
        f"- Latest weight: {facts.weight_latest_kg if facts.weight_latest_kg is not None else 'n/a'} kg\n"
        f"- Sessions completed (last 7 days): {facts.completed_sessions_7d}\n"
        "- Note: KL/Selangor heat and humidity affect pace and hydration; "
        "factor them into advice if the athlete mentions hot or rainy weather."
    )
