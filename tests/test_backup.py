"""backup.py tests — atomic roundtrip + retention pruning."""

from datetime import date, timedelta
from pathlib import Path

from backup import backup_db, prune, restore_db
from db import init_db, save_log


def test_backup_restore_roundtrip(tmp_path) -> None:
    db_path = tmp_path / "live" / "trainer_data.db"
    conn = init_db(db_path)
    log_id = save_log(
        conn, date="2026-07-10", user_id=1, ai_response="ok",
        distance_km=10.42, completed=1, verified=1,
    )
    conn.close()

    backup_dir = tmp_path / "backups"
    backup_file = backup_db(db_path, backup_dir)
    assert backup_file.exists()
    assert backup_file.name == f"trainer_data_{date.today().isoformat()}.db"

    # Wipe the live DB, restore, verify data + schema survived.
    db_path.unlink()
    assert not db_path.exists()
    restore_db(backup_file, db_path)
    conn = init_db(db_path)
    row = conn.execute("SELECT * FROM daily_logs WHERE id = ?", (log_id,)).fetchone()
    assert row is not None
    assert row["distance_km"] == 10.42
    assert row["verified"] == 1
    tables = {
        r["name"]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert "schema_migrations" in tables
    conn.close()


def test_backup_is_atomic_snapshot(tmp_path) -> None:
    """Backup of a live DB is consistent even with data written after."""
    db_path = tmp_path / "trainer_data.db"
    conn = init_db(db_path)
    save_log(conn, date="2026-07-10", user_id=1, ai_response="before", distance_km=5.0)
    backup_file = backup_db(db_path, tmp_path / "backups")
    # Write more after the snapshot — the backup must not contain it.
    save_log(conn, date="2026-07-11", user_id=1, ai_response="after", distance_km=6.0)
    conn.close()

    restored = tmp_path / "restored.db"
    restore_db(backup_file, restored)
    conn = init_db(restored)
    rows = conn.execute("SELECT ai_response FROM daily_logs").fetchall()
    assert [r["ai_response"] for r in rows] == ["before"]
    conn.close()


def test_prune_removes_old_keeps_new(tmp_path) -> None:
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    old = backup_dir / f"trainer_data_{(date.today() - timedelta(days=31)).isoformat()}.db"
    new = backup_dir / f"trainer_data_{date.today().isoformat()}.db"
    old.write_bytes(b"x")
    new.write_bytes(b"y")

    removed = prune(backup_dir, retention_days=30)
    assert removed == [old]
    assert not old.exists()
    assert new.exists()
    assert prune(backup_dir, retention_days=30) == []
