"""Race-time prediction — Riegel formula, code-computed, never AI math.

    T2 = T1 × (D2 / D1) ^ b        (Riegel, Runner's World 1977)

- Input: the BEST verified performance anchor (race result preferred; else
  the fastest verified effort). Training runs are excluded by `verified=0`.
- Validity: anchors inside Riegel's 3.5–230 min endurance range.
- With ≥2 anchors the exponent is REFIT from the athlete's own data
  (b = ln(T2/T1) / ln(D2/D1)), clamped to [1.0, 1.15] — this fixes the known
  1.06 over-prediction bias for longer distances.
- Output: a ±5% BAND, never a single number.
- Never auto-changes the target — `target_proposal()` builds a proposal the
  athlete confirms.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

DEFAULT_EXPONENT = 1.06
BAND_PCT = 0.05
MIN_ANCHOR_SEC = 3.5 * 60  # Riegel validity window
MAX_ANCHOR_SEC = 230 * 60
EXPO_MIN, EXPO_MAX = 1.0, 1.15
HALF_MARATHON_KM = 21.0975


@dataclass(frozen=True)
class Prediction:
    distance_km: float
    predicted_sec: float
    low_sec: float
    high_sec: float
    exponent: float
    anchor_source: str


def riegel(t1_sec: float, d1_km: float, d2_km: float, exponent: float = DEFAULT_EXPONENT) -> float:
    return t1_sec * (d2_km / d1_km) ** exponent


def _sorted_verified_anchors(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM performance_anchors WHERE verified = 1 "
        "AND time_sec BETWEEN ? AND ? ORDER BY distance_km ASC",
        (MIN_ANCHOR_SEC, MAX_ANCHOR_SEC),
    ).fetchall()
    return [dict(row) for row in rows]


def refit_exponent(anchors: list[dict]) -> float:
    """Fit b from the two furthest-apart anchors; clamp to sane range."""
    if len(anchors) < 2:
        return DEFAULT_EXPONENT
    first, last = anchors[0], anchors[-1]
    if last["distance_km"] <= first["distance_km"] or last["time_sec"] <= first["time_sec"]:
        return DEFAULT_EXPONENT
    b = math.log(last["time_sec"] / first["time_sec"]) / math.log(
        last["distance_km"] / first["distance_km"]
    )
    return min(max(b, EXPO_MIN), EXPO_MAX)


def best_anchor(anchors: list[dict]) -> dict | None:
    """Race results preferred; within the pool, the fastest effort wins."""
    races = [a for a in anchors if a.get("source") == "race"]
    pool = races or anchors
    if not pool:
        return None
    return max(pool, key=lambda a: a["distance_km"] / a["time_sec"])


def predict(conn, distance_km: float = HALF_MARATHON_KM) -> Prediction | None:
    anchors = _sorted_verified_anchors(conn)
    anchor = best_anchor(anchors)
    if anchor is None:
        return None
    exponent = refit_exponent(anchors)
    t2 = riegel(anchor["time_sec"], anchor["distance_km"], distance_km, exponent)
    return Prediction(
        distance_km=distance_km,
        predicted_sec=t2,
        low_sec=t2 * (1 - BAND_PCT),
        high_sec=t2 * (1 + BAND_PCT),
        exponent=round(exponent, 4),
        anchor_source=anchor.get("source") or "verified_effort",
    )


def format_seconds(sec: float) -> str:
    total = int(round(sec))
    hours, rem = divmod(total, 3600)
    minutes, seconds = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def format_prediction(prediction: Prediction) -> str:
    return (
        f"Predicted {prediction.distance_km:.1f} km: "
        f"**{format_seconds(prediction.predicted_sec)}** "
        f"(band {format_seconds(prediction.low_sec)} – {format_seconds(prediction.high_sec)}, "
        f"±{int(BAND_PCT * 100)}%) "
        f"from {prediction.anchor_source} (exponent {prediction.exponent})"
    )


def target_proposal(
    prediction: Prediction,
    current_target_sec: float,
    label: str = "current target",
    threshold_sec: float = 30.0,
) -> str | None:
    """Proposal when prediction differs materially from the target. The
    athlete confirms — the target is never changed automatically."""
    diff = prediction.predicted_sec - current_target_sec
    if abs(diff) < threshold_sec:
        return None
    direction = "faster than" if diff < 0 else "slower than"
    return (
        f"Your prediction ({format_seconds(prediction.predicted_sec)}) is {direction} "
        f"your {label} ({format_seconds(current_target_sec)}). "
        "Update the target?"
    )
