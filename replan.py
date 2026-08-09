"""Milestone re-plan gate — data-driven proposals every 4–6 weeks.

Every value is computed in code (facts, rollups, prediction). The output is
a set of user-actionable proposals the athlete CONFIRMS — nothing is ever
auto-applied. The goal stays honest because data drives it.
"""

from __future__ import annotations

from dataclasses import dataclass

from guardrails import volume_increase_within_cap
from predict import Prediction, format_seconds, target_proposal

PACE_PROPOSAL_THRESHOLD_SEC = 10.0
WEIGHT_TREND_THRESHOLD_KG = -0.5


@dataclass(frozen=True)
class Proposal:
    title: str
    detail: str
    action: str  # command the athlete can run to act on it


def pace_proposal(
    avg_pace_sec_km: float | None,
    target_pace_sec_km: float,
    label: str = "race target",
) -> Proposal | None:
    """Faster/slower than target by ≥10 s/km → propose a target update."""
    if avg_pace_sec_km is None:
        return None
    delta = target_pace_sec_km - avg_pace_sec_km  # >0 → running faster than target
    if delta >= PACE_PROPOSAL_THRESHOLD_SEC:
        suggested = target_pace_sec_km - delta
        return Proposal(
            "Pace improvement",
            f"Last 4 weeks avg {format_seconds(avg_pace_sec_km)} — {delta:.0f} s/km "
            f"faster than your {label} ({format_seconds(target_pace_sec_km)}). "
            f"Propose updating the target to {format_seconds(suggested)}?",
            "/target",
        )
    if delta <= -PACE_PROPOSAL_THRESHOLD_SEC:
        return Proposal(
            "Pace gap",
            f"Last 4 weeks avg {format_seconds(avg_pace_sec_km)} is "
            f"{abs(delta):.0f} s/km slower than target "
            f"({format_seconds(target_pace_sec_km)}). Adjust the target or add "
            "recovery before the next block.",
            "/target",
        )
    return None


def volume_proposal(this_week_km: float, prev_week_km: float) -> Proposal | None:
    if prev_week_km > 0 and not volume_increase_within_cap(this_week_km, prev_week_km):
        pct = (this_week_km - prev_week_km) / prev_week_km * 100.0
        return Proposal(
            "Volume spike",
            f"This week {this_week_km:.1f} km is +{pct:.0f}% vs last week "
            f"({prev_week_km:.1f}) — over the 10% hard cap. Cut back.",
            "/today",
        )
    return None


def weight_proposal(weight_trend_kg: float | None, weeks: int = 4) -> Proposal | None:
    """Underweight athlete: a losing trend is a nutrition red flag."""
    if weight_trend_kg is None:
        return None
    if weight_trend_kg < WEIGHT_TREND_THRESHOLD_KG:
        return Proposal(
            "Weight trend",
            f"Weight is trending down ({weight_trend_kg:+.1f} kg over {weeks} "
            "weeks) — a losing trend while building for an endurance goal is a "
            "nutrition red flag; bump calories to a small consistent surplus "
            "(protein spread across the day).",
            "/weight",
        )
    return None


def prediction_proposal(prediction: Prediction | None, target_sec: float) -> Proposal | None:
    if prediction is None:
        return None
    text = target_proposal(prediction, target_sec)
    if text is None:
        return None
    return Proposal("Prediction gap", text, "/predict")


def build_replan_report(
    *,
    pace_avg_sec_km: float | None,
    target_pace_sec_km: float,
    this_week_km: float,
    prev_week_km: float,
    weight_trend_kg: float | None,
    prediction: Prediction | None = None,
    target_sec: float | None = None,
) -> list[Proposal]:
    """All actionable proposals for this gate. Empty list = nothing to do."""
    proposals: list[Proposal | None] = [
        pace_proposal(pace_avg_sec_km, target_pace_sec_km),
        volume_proposal(this_week_km, prev_week_km),
        weight_proposal(weight_trend_kg),
        prediction_proposal(prediction, target_sec) if target_sec else None,
    ]
    return [p for p in proposals if p is not None]
