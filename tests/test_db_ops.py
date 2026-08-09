"""Phase 2 db additions — save_log, get_recent_history, weekly rollups."""

from datetime import date, timedelta

from db import (
    compute_weekly_rollup,
    get_recent_history,
    init_db,
    save_log,
    store_weekly_rollup,
)


def _seed_week(conn, user_id: int = 1) -> str:
    week = "2026-07-06"
    save_log(
        conn, date="2026-07-06", user_id=user_id, user_input="easy 6k",
        ai_response="ok", rpe=5, fatigue_level=4, distance_km=6.0,
        moving_time_min=45.0, completed=1,
    )
    save_log(
        conn, date="2026-07-08", user_id=user_id, user_input="tempo",
        ai_response="ok", rpe=7, fatigue_level=6, distance_km=8.0,
        moving_time_min=50.0, completed=1,
    )
    save_log(
        conn, date="2026-07-08", user_id=user_id, user_input="weight only",
        ai_response="ok", weight_kg=55.0, completed=0,
    )
    save_log(
        conn, date="2026-07-10", user_id=user_id, user_input="long run",
        ai_response="ok", rpe=6, fatigue_level=5, distance_km=12.0,
        moving_time_min=84.0, completed=1, verified=1,
    )
    return week


def test_save_log_computes_pace_in_code() -> None:
    conn = init_db(":memory:")
    log_id = save_log(
        conn, date="2026-07-10", user_id=1, user_input="long",
        ai_response="ok", distance_km=10.42, moving_time_min=72.6,
        completed=1, verified=1,
    )
    row = conn.execute("SELECT * FROM daily_logs WHERE id = ?", (log_id,)).fetchone()
    assert row["avg_pace_sec_km"] == 418  # 72.6 * 60 / 10.42 = 418.04...


def test_save_log_without_distance_keeps_pace_null() -> None:
    conn = init_db(":memory:")
    log_id = save_log(conn, date="2026-07-08", user_id=1, ai_response="ok", rpe=5)
    row = conn.execute("SELECT * FROM daily_logs WHERE id = ?", (log_id,)).fetchone()
    assert row["avg_pace_sec_km"] is None


def test_recent_history_window() -> None:
    conn = init_db(":memory:")
    today = date.today()
    save_log(conn, date=(today - timedelta(days=10)).isoformat(), user_id=1, ai_response="old")
    save_log(conn, date=(today - timedelta(days=2)).isoformat(), user_id=1, ai_response="recent")
    history = get_recent_history(conn, 1, days=7)
    assert [row["ai_response"] for row in history] == ["recent"]


def test_rollup_numbers_on_synthetic_week() -> None:
    conn = init_db(":memory:")
    week = _seed_week(conn)
    rollup = compute_weekly_rollup(conn, 1, week)
    assert rollup["volume_km"] == 26.0  # 6 + 8 + 12 (completed only)
    assert rollup["avg_rpe"] == 6.0  # (5 + 7 + 6) / 3
    assert rollup["avg_fatigue"] == 5.0  # (4 + 6 + 5) / 3
    assert rollup["completed_sessions"] == 3
    assert rollup["long_run_km"] == 12.0
    assert rollup["weight_trend"] == 0.0  # single weight entry


def test_rollup_weight_trend() -> None:
    conn = init_db(":memory:")
    save_log(conn, date="2026-07-06", user_id=1, ai_response="", weight_kg=55.0)
    save_log(conn, date="2026-07-10", user_id=1, ai_response="", weight_kg=55.8)
    rollup = compute_weekly_rollup(conn, 1, "2026-07-06")
    assert rollup["weight_trend"] == 0.8


def test_store_weekly_rollup_upserts() -> None:
    conn = init_db(":memory:")
    week = "2026-07-06"
    store_weekly_rollup(
        conn, week,
        {"volume_km": 10.0, "avg_rpe": 5.0, "avg_fatigue": 4.0,
         "weight_trend": 0.5, "completed_sessions": 2, "long_run_km": 6.0},
    )
    store_weekly_rollup(
        conn, week,
        {"volume_km": 12.0, "avg_rpe": 6.0, "avg_fatigue": 5.0,
         "weight_trend": 0.8, "completed_sessions": 3, "long_run_km": 8.0},
    )
    rows = conn.execute("SELECT * FROM weekly_rollups").fetchall()
    assert len(rows) == 1
    assert rows[0]["volume_km"] == 12.0
    assert rows[0]["completed_sessions"] == 3
