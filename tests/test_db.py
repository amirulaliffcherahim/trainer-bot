"""db.py tests — migration runner creates the full v2 schema, idempotently."""

import sqlite3

import pytest

from db import EXPECTED_TABLES, init_db


def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {row["name"] for row in rows}


def test_init_creates_all_tables(tmp_path) -> None:
    conn = init_db(tmp_path / "test.db")
    tables = _table_names(conn)
    for name in EXPECTED_TABLES:
        assert name in tables, f"missing table: {name}"


def test_init_idempotent(tmp_path) -> None:
    path = tmp_path / "test.db"
    init_db(path)
    conn = init_db(path)
    from db import MIGRATIONS_DIR

    expected = {p.name for p in MIGRATIONS_DIR.glob("*.sql")}
    applied = {r["name"] for r in conn.execute("SELECT name FROM schema_migrations")}
    assert applied == expected  # future migrations must not break this test


def test_review_indexes_created(tmp_path) -> None:
    conn = init_db(tmp_path / "test.db")
    names = {
        r["name"]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
    }
    assert "idx_workout_plan_date" in names
    assert "idx_perf_anchors_verified_dist" in names


def test_init_in_memory() -> None:
    conn = init_db(":memory:")
    assert "daily_logs" in _table_names(conn)


def test_rpe_check_constraint_enforced(tmp_path) -> None:
    conn = init_db(tmp_path / "test.db")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO daily_logs (date, user_id, ai_response, rpe) "
            "VALUES ('2026-01-01', 1, 'x', 15)"
        )
        conn.commit()


def test_db_file_created_in_parent_dir(tmp_path) -> None:
    path = tmp_path / "nested" / "dir" / "test.db"
    conn = init_db(path)
    assert path.exists()
    conn.close()
