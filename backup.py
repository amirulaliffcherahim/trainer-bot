"""Atomic SQLite daily backups with retention pruning.

Uses SQLite's online backup API (src.backup) — consistent even while the
bot is writing. Retention: 30 days by default. Restore copies a backup file
back (bot must be stopped).
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
from datetime import date, timedelta
from pathlib import Path

DEFAULT_RETENTION_DAYS = 30


def backup_db(
    db_path: str | Path,
    backup_dir: str | Path,
    *,
    retention_days: int = DEFAULT_RETENTION_DAYS,
) -> Path:
    """Atomic online backup of db_path into backup_dir. Returns the file."""
    out = Path(backup_dir)
    out.mkdir(parents=True, exist_ok=True)
    target = out / f"trainer_data_{date.today().isoformat()}.db"

    source = sqlite3.connect(str(db_path))
    try:
        destination = sqlite3.connect(str(target))
        try:
            with destination:
                source.backup(destination)  # consistent snapshot while live
        finally:
            destination.close()
    finally:
        source.close()

    prune(out, retention_days)
    return target


def prune(backup_dir: str | Path, retention_days: int = DEFAULT_RETENTION_DAYS) -> list[Path]:
    """Delete backups older than retention_days. Returns removed files."""
    cutoff = date.today() - timedelta(days=retention_days)
    removed: list[Path] = []
    for file in sorted(Path(backup_dir).glob("trainer_data_*.db")):
        try:
            stamp = date.fromisoformat(file.stem.split("_")[-1])
        except ValueError:
            continue
        if stamp < cutoff:
            file.unlink()
            removed.append(file)
    return removed


def restore_db(backup_path: str | Path, db_path: str | Path) -> None:
    """Restore a backup over the live DB. Bot must be stopped."""
    shutil.copy2(str(backup_path), str(db_path))


def main() -> None:
    parser = argparse.ArgumentParser(description="Backup the trainer SQLite database")
    parser.add_argument("db_path", help="path to the live database")
    parser.add_argument("backup_dir", help="directory to store backups")
    parser.add_argument("--retention-days", type=int, default=DEFAULT_RETENTION_DAYS)
    args = parser.parse_args()
    target = backup_db(args.db_path, args.backup_dir, retention_days=args.retention_days)
    print(f"Backup written: {target}")


if __name__ == "__main__":
    main()
