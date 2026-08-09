"""test_workouts.py — phase-aware /today queries."""

from db import init_db
from workouts import format_today, get_phase, get_workout, parse_pace_sec_km


def _seed(conn):
    conn.execute(
        "INSERT INTO training_phases (phase_name, start_date, end_date, focus) "
        "VALUES ('base', '2025-08-01', '2026-07-26', 'easy miles, strength')"
    )
    conn.execute(
        "INSERT INTO training_phases (phase_name, start_date, end_date, focus) "
        "VALUES ('hm_block', '2026-07-27', '2026-11-01', 'build + taper')"
    )
    conn.execute(
        "INSERT INTO workout_plan (date, day_type, session_type, description, "
        "prescribed_km, target_pace) "
        "VALUES ('2026-07-28', 'tuesday', 'easy_run', '4 km easy', 4.0, '7:45 min/km')"
    )
    conn.commit()


def test_parse_pace_sec_km() -> None:
    assert parse_pace_sec_km("7:10") == 430
    assert parse_pace_sec_km("7:10/km") == 430
    assert parse_pace_sec_km("7:10 min/km") == 430
    assert parse_pace_sec_km(None) is None
    assert parse_pace_sec_km("nope") is None


def test_get_phase_selects_spanning_row() -> None:
    conn = init_db(":memory:")
    _seed(conn)
    assert get_phase(conn, "2026-03-01")["phase_name"] == "base"
    assert get_phase(conn, "2026-08-01")["phase_name"] == "hm_block"
    assert get_phase(conn, "2025-01-01") is None


def test_get_workout_by_date() -> None:
    conn = init_db(":memory:")
    _seed(conn)
    assert get_workout(conn, "2026-07-28")["session_type"] == "easy_run"
    assert get_workout(conn, "2026-07-29") is None


def test_format_today_full() -> None:
    conn = init_db(":memory:")
    _seed(conn)
    text = format_today(
        "2026-07-28",
        get_phase(conn, "2026-07-28"),
        get_workout(conn, "2026-07-28"),
        target_pace="2:30:00 @ 7:06/km",
    )
    assert "hm_block" in text
    assert "easy_run" in text
    assert "4.0 km" in text
    assert "7:45" in text


def test_format_today_graceful_when_empty() -> None:
    conn = init_db(":memory:")
    text = format_today("2026-07-28", None, None)
    assert "not seeded" in text
    assert "No workout scheduled" in text
