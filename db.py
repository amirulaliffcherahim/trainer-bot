"""SQLite access + forward-only migration runner.

Security: the database contains personal health data. It must never be
committed to git (see .gitignore) and never leave the server.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

# Every table the bot relies on (created by migrations/001_init.sql).
EXPECTED_TABLES = (
    "daily_logs",
    "athlete_profile",
    "training_phases",
    "workout_plan",
    "weekly_rollups",
    "kb_chunks",
    "eval_cases",
    "suggestions_log",
    "challenges",
    "target_history",
    "performance_anchors",
    "schema_migrations",
)


def get_conn(db_path: str | Path) -> sqlite3.Connection:
    """Open a connection with row access and foreign keys enabled."""
    if db_path == ":memory:":
        conn = sqlite3.connect(":memory:")
    else:
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # WAL + busy timeout: Telegram handlers and background jobs (recap push,
    # rollups) share the DB; without these, concurrent writers can throw
    # sqlite3.OperationalError: database is locked.
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def _ensure_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            applied_at TEXT DEFAULT (datetime('now'))
        )
        """
    )
    conn.commit()


def _applied_migrations(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM schema_migrations").fetchall()
    return {row["name"] for row in rows}


def init_db(db_path: str | Path) -> sqlite3.Connection:
    """Apply all pending migrations and return a connection.

    Idempotent: already-applied migrations are skipped. New migrations are
    applied in filename order.
    """
    conn = get_conn(db_path)
    _ensure_migrations_table(conn)
    applied = _applied_migrations(conn)
    pending = sorted(p for p in MIGRATIONS_DIR.glob("*.sql") if p.name not in applied)
    for migration in pending:
        conn.executescript(migration.read_text(encoding="utf-8"))
        conn.execute(
            "INSERT INTO schema_migrations (name) VALUES (?)", (migration.name,)
        )
        conn.commit()
    return conn


# --- Phase 2: log persistence, history, rollups ---------------------------


def save_log(
    conn: sqlite3.Connection,
    *,
    date: str,
    user_id: int,
    user_input: str | None = None,
    ai_response: str = "",
    rpe: int | None = None,
    fatigue_level: int | None = None,
    weight_kg: float | None = None,
    sleep_hours: float | None = None,
    session_type: str | None = None,
    distance_km: float | None = None,
    moving_time_min: float | None = None,
    completed: int = 0,
    verified: int = 0,
    model_used: str | None = None,
    prompt_version: str | None = None,
    persona_drafts: str | None = None,
    raw_payload: str | None = None,
) -> int:
    """Insert a daily log row. avg_pace_sec_km is COMPUTED in code from
    distance + moving time — the LLM never supplies pace."""
    avg_pace_sec_km = None
    if distance_km and moving_time_min:
        avg_pace_sec_km = int(round(moving_time_min * 60 / distance_km))
    cursor = conn.execute(
        """
        INSERT INTO daily_logs (
            date, user_id, user_input, ai_response, rpe, fatigue_level,
            weight_kg, sleep_hours, session_type, distance_km, moving_time_min,
            avg_pace_sec_km, completed, verified, model_used, prompt_version,
            persona_drafts, raw_payload
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            date,
            user_id,
            user_input,
            ai_response,
            rpe,
            fatigue_level,
            weight_kg,
            sleep_hours,
            session_type,
            distance_km,
            moving_time_min,
            avg_pace_sec_km,
            completed,
            verified,
            model_used,
            prompt_version,
            persona_drafts,
            raw_payload,
        ),
    )
    conn.commit()
    return int(cursor.lastrowid)


def get_recent_history(
    conn: sqlite3.Connection, user_id: int, days: int = 21
) -> list[dict]:
    """Recent daily logs (newest last) — the raw rows feeding compute_facts.

    Default 21 days: compute_facts needs last week's rows for volume/fatigue
    deltas and up to 6 verified runs for pace trends; a 7-day window would
    starve those numbers.
    """
    rows = conn.execute(
        """
        SELECT * FROM daily_logs
        WHERE user_id = ? AND date >= date('now', ?)
        ORDER BY date ASC, id ASC
        """,
        (user_id, f"-{days} days"),
    ).fetchall()
    return [dict(row) for row in rows]


def compute_weekly_rollup(conn: sqlite3.Connection, user_id: int, week_start: str) -> dict:
    """Aggregate one ISO week (week_start inclusive, +7 days exclusive)."""
    row = conn.execute(
        """
        SELECT
            COALESCE(SUM(CASE WHEN completed = 1 THEN distance_km ELSE 0 END), 0) AS volume_km,
            AVG(rpe) AS avg_rpe,
            AVG(fatigue_level) AS avg_fatigue,
            SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) AS completed_sessions,
            MAX(distance_km) AS long_run_km
        FROM daily_logs
        WHERE user_id = ? AND date >= ? AND date < date(?, '+7 days')
        """,
        (user_id, week_start, week_start),
    ).fetchone()
    rollup = dict(row)

    first = conn.execute(
        "SELECT weight_kg FROM daily_logs WHERE user_id = ? AND date >= ? "
        "AND date < date(?, '+7 days') AND weight_kg IS NOT NULL "
        "ORDER BY date ASC, id ASC LIMIT 1",
        (user_id, week_start, week_start),
    ).fetchone()
    last = conn.execute(
        "SELECT weight_kg FROM daily_logs WHERE user_id = ? AND date >= ? "
        "AND date < date(?, '+7 days') AND weight_kg IS NOT NULL "
        "ORDER BY date DESC, id DESC LIMIT 1",
        (user_id, week_start, week_start),
    ).fetchone()
    rollup["weight_trend"] = None
    if first is not None and last is not None:
        rollup["weight_trend"] = round(last["weight_kg"] - first["weight_kg"], 2)
    for key in ("avg_rpe", "avg_fatigue", "long_run_km"):
        if rollup.get(key) is not None:
            rollup[key] = round(float(rollup[key]), 2)
    rollup["volume_km"] = round(float(rollup["volume_km"]), 2)
    rollup["completed_sessions"] = int(rollup["completed_sessions"] or 0)
    return rollup


def store_weekly_rollup(conn: sqlite3.Connection, week_start: str, rollup: dict) -> None:
    """Upsert a weekly rollup (idempotent per week_start)."""
    conn.execute(
        """
        INSERT INTO weekly_rollups (
            week_start, volume_km, avg_rpe, avg_fatigue, weight_trend,
            completed_sessions, long_run_km
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(week_start) DO UPDATE SET
            volume_km = excluded.volume_km,
            avg_rpe = excluded.avg_rpe,
            avg_fatigue = excluded.avg_fatigue,
            weight_trend = excluded.weight_trend,
            completed_sessions = excluded.completed_sessions,
            long_run_km = excluded.long_run_km
        """,
        (
            week_start,
            rollup["volume_km"],
            rollup["avg_rpe"],
            rollup["avg_fatigue"],
            rollup["weight_trend"],
            rollup["completed_sessions"],
            rollup["long_run_km"],
        ),
    )
    conn.commit()
