"""retention.py tests — streaks, month totals, Sunday recap, silence."""

from datetime import date, timedelta

from db import init_db, save_log
from retention import (
    days_since_last_log,
    month_km,
    silence_nudge,
    streak_days,
    sunday_recap,
)

TODAY = date(2026, 7, 15)  # Wednesday


def _log(conn, when: date, *, km: float = 5.0, rpe: int | None = None) -> None:
    save_log(
        conn,
        date=when.isoformat(),
        user_id=1,
        user_input="run",
        ai_response="ok",
        distance_km=km,
        rpe=rpe,
        completed=1,
    )


def test_streak_contiguous_days() -> None:
    conn = init_db(":memory:")
    for i in range(4):
        _log(conn, TODAY - timedelta(days=i))
    assert streak_days(conn, 1, TODAY) == 4


def test_streak_breaks_on_gap() -> None:
    conn = init_db(":memory:")
    _log(conn, TODAY)
    _log(conn, TODAY - timedelta(days=2))  # gap on day 1
    assert streak_days(conn, 1, TODAY) == 1


def test_streak_counts_from_yesterday_when_today_unlogged() -> None:
    conn = init_db(":memory:")
    _log(conn, TODAY - timedelta(days=1))
    _log(conn, TODAY - timedelta(days=2))
    assert streak_days(conn, 1, TODAY) == 2  # today unlogged → streak alive until midnight


def test_month_km_counts_completed_only() -> None:
    conn = init_db(":memory:")
    _log(conn, TODAY, km=10.0)
    _log(conn, TODAY, km=5.0)
    save_log(conn, date=TODAY.isoformat(), user_id=1, ai_response="ok", distance_km=99.0, completed=0)
    _log(conn, date(2026, 6, 30), km=50.0)  # previous month excluded
    assert month_km(conn, 1, TODAY) == 15.0


def test_days_since_last_log() -> None:
    conn = init_db(":memory:")
    _log(conn, TODAY - timedelta(days=4))
    assert days_since_last_log(conn, 1, TODAY) == 4
    assert days_since_last_log(conn, 2, TODAY) is None  # no logs at all


def test_sunday_recap_content() -> None:
    conn = init_db(":memory:")
    for i in range(5):
        _log(conn, TODAY - timedelta(days=i), km=5.0 + i, rpe=6)
    recap = sunday_recap(conn, 1, week_start="2026-07-13", today=TODAY)
    assert "Sunday recap" in recap
    assert "18.0 km" in recap  # window Jul 13-15: 5+6+7
    assert "3" in recap  # sessions in window
    assert "35.0 km" in recap  # month total (all 5 logs, Jul 11-15)
    assert "Streak" in recap


def test_sunday_recap_milestone_and_challenge() -> None:
    conn = init_db(":memory:")
    for i in range(4):
        _log(conn, TODAY - timedelta(days=i), km=15.0)
    from challenges import ChallengeTemplate

    challenge = ChallengeTemplate("runner", "any", "Strides week", "4x100m after easy runs", "done")
    recap = sunday_recap(
        conn, 1, week_start="2026-07-13", today=TODAY, challenge=challenge
    )
    assert "milestone" in recap  # 60 km in July
    assert "Strides week" in recap


def test_silence_nudge_threshold() -> None:
    conn = init_db(":memory:")
    _log(conn, TODAY - timedelta(days=4))
    nudge = silence_nudge(conn, 1, today=TODAY)
    assert nudge is not None
    assert "4 days" in nudge
    _log(conn, TODAY - timedelta(days=1))
    assert silence_nudge(conn, 1, today=TODAY) is None
    assert silence_nudge(conn, 2, today=TODAY) is None  # no history
