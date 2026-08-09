"""seed_plan.py tests — idempotent calendar seeding + validation."""

import pytest

from db import init_db
from seed_plan import seed_plan

PLAN = {
    "phases": [
        {"name": "base", "start": "2026-01-01", "end": "2026-07-26", "focus": "easy"},
        {"name": "build", "start": "2026-07-27", "end": "2026-10-25"},
    ],
    "workouts": [
        {
            "date": "2026-07-28",
            "day_type": "tuesday",
            "session_type": "easy_run",
            "description": "4 km easy",
            "prescribed_km": 4.0,
            "target_pace": "7:45 min/km",
        },
        {
            "date": "2026-08-01",
            "session_type": "long_run",
            "prescribed_km": 8.0,
        },
    ],
}


def test_seed_plan_inserts_phases_and_workouts() -> None:
    conn = init_db(":memory:")
    result = seed_plan(conn, PLAN)
    assert result == {"phases": 2, "workouts": 2, "skipped": 0}
    assert conn.execute("SELECT COUNT(*) AS n FROM training_phases").fetchone()["n"] == 2
    assert conn.execute("SELECT COUNT(*) AS n FROM workout_plan").fetchone()["n"] == 2
    row = conn.execute(
        "SELECT * FROM workout_plan WHERE date = '2026-07-28'"
    ).fetchone()
    assert row["prescribed_km"] == 4.0
    assert row["session_type"] == "easy_run"


def test_seed_plan_idempotent() -> None:
    conn = init_db(":memory:")
    seed_plan(conn, PLAN)
    result = seed_plan(conn, PLAN)
    assert result["workouts"] == 0  # dates already present
    assert result["skipped"] == 2
    assert conn.execute("SELECT COUNT(*) AS n FROM workout_plan").fetchone()["n"] == 2
    # Phases keyed by name: still exactly one row per name.
    assert conn.execute("SELECT COUNT(*) AS n FROM training_phases").fetchone()["n"] == 2


def test_seed_plan_phase_replacement() -> None:
    conn = init_db(":memory:")
    seed_plan(conn, PLAN)
    updated = {
        "phases": [
            {"name": "base", "start": "2026-01-01", "end": "2026-07-20", "focus": "revised"}
        ],
        "workouts": [],
    }
    seed_plan(conn, updated)
    row = conn.execute("SELECT * FROM training_phases WHERE phase_name = 'base'").fetchone()
    assert row["end_date"] == "2026-07-20"
    assert conn.execute("SELECT COUNT(*) AS n FROM training_phases").fetchone()["n"] == 2


def test_seed_plan_validates_required_keys() -> None:
    conn = init_db(":memory:")
    with pytest.raises(ValueError):
        seed_plan(conn, {"phases": [{"name": "x"}], "workouts": []})
    with pytest.raises(ValueError):
        seed_plan(conn, {"phases": [], "workouts": [{"date": "2026-01-01"}]})
