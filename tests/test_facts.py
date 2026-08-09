"""facts.py tests — pure functions on synthetic rows, deterministic dates."""

from datetime import date

from facts import FactsBlock, compute_facts, format_facts_block

# 2026-07-13 is a Monday → clean ISO week boundaries.
TODAY = date(2026, 7, 13)
THIS_WEEK = ["2026-07-13", "2026-07-14", "2026-07-15"]
LAST_WEEK = ["2026-07-06", "2026-07-08"]
# 7-day RPE window starts 2026-07-07 (today - 6 days).


def _row(
    log_date,
    *,
    rpe=None,
    fatigue=None,
    weight=None,
    distance=None,
    pace=None,
    completed=1,
    verified=1,
):
    return {
        "date": log_date,
        "rpe": rpe,
        "fatigue_level": fatigue,
        "weight_kg": weight,
        "distance_km": distance,
        "avg_pace_sec_km": pace,
        "completed": completed,
        "verified": verified,
    }


def test_facts_on_synthetic_two_weeks() -> None:
    logs = [
        _row("2026-07-06", rpe=5, fatigue=4, distance=6.0, pace=450),  # outside 7d window
        _row("2026-07-08", rpe=6, fatigue=5, distance=5.0, pace=440),
        _row("2026-07-13", rpe=6, fatigue=5, distance=7.0, pace=430, weight=55.0),
        _row("2026-07-14", rpe=7, fatigue=6, distance=4.0, pace=420, weight=55.4),
    ]
    facts = compute_facts(logs, today=TODAY)
    assert facts.avg_rpe_7d == 6.3  # (6 + 6 + 7) / 3 — 07-06 outside window
    assert facts.fatigue_this_week == 5.5  # (5 + 6) / 2
    assert facts.fatigue_last_week == 4.5  # (4 + 5) / 2
    assert facts.volume_km_this_week == 11.0  # 7 + 4
    assert facts.volume_km_last_week == 11.0  # 6 + 5
    assert facts.volume_delta_pct == 0.0
    assert facts.pace_avg_last3_sec_km == 430.0  # mean(440, 430, 420)
    assert facts.pace_avg_prev3_sec_km == 450.0  # mean(450)
    assert facts.weight_latest_kg == 55.4
    assert facts.completed_sessions_7d == 3  # 07-08, 07-13, 07-14


def test_unverified_runs_excluded_from_pace() -> None:
    logs = [
        _row("2026-07-13", distance=7.0, pace=400, verified=0),
        _row("2026-07-14", distance=4.0, pace=420, verified=1),
    ]
    facts = compute_facts(logs, today=TODAY)
    assert facts.pace_avg_last3_sec_km == 420.0
    assert facts.volume_km_this_week == 11.0  # volume counts completed, not verified


def test_empty_history_returns_zeroed_block() -> None:
    facts = compute_facts([], today=TODAY)
    assert facts.avg_rpe_7d is None
    assert facts.volume_km_this_week == 0.0
    assert facts.volume_delta_pct is None
    assert facts.completed_sessions_7d == 0


def test_volume_delta_pct_guards_division_by_zero() -> None:
    logs = [_row("2026-07-13", distance=5.0)]
    facts = compute_facts(logs, today=TODAY)
    assert facts.volume_km_last_week == 0.0
    assert facts.volume_delta_pct is None


def test_format_facts_block_renders_pace_and_labels() -> None:
    facts = FactsBlock(
        avg_rpe_7d=6.2,
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
    block = format_facts_block(facts)
    assert "6:58/km" in block
    assert "7:05/km" in block
    assert "+8.8%" in block
    assert "do not recompute" in block
    assert "KL/Selangor" in block
