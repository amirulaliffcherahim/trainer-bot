"""Seed the training calendar from a YAML plan — phases + week-by-week
workouts. Idempotent: existing dates are skipped, phases by name replaced.

Your plan file is YOUR data — it never ships in the repo (gitignored).
See seed_plan.example.yaml for the shape.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from db import init_db


def seed_plan(conn, plan: dict) -> dict:
    """Insert training_phases + workout_plan rows. Returns counts."""
    result = {"phases": 0, "workouts": 0, "skipped": 0}

    phases = plan.get("phases", [])
    for phase in phases:
        required = ("name", "start", "end")
        missing = [k for k in required if not phase.get(k)]
        if missing:
            raise ValueError(f"phase missing keys {missing}: {phase}")
        # Phases are keyed by name: replace any existing row with the same name.
        conn.execute("DELETE FROM training_phases WHERE phase_name = ?", (phase["name"],))
        conn.execute(
            "INSERT INTO training_phases (phase_name, start_date, end_date, focus, "
            "volume_range, pace_target, rules_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                phase["name"],
                phase["start"],
                phase["end"],
                phase.get("focus"),
                phase.get("volume_range"),
                phase.get("pace_target"),
                phase.get("rules_json"),
            ),
        )
        result["phases"] += 1
    conn.commit()

    workouts = plan.get("workouts", [])
    for workout in workouts:
        required = ("date", "session_type")
        missing = [k for k in required if not workout.get(k)]
        if missing:
            raise ValueError(f"workout missing keys {missing}: {workout}")
        exists = conn.execute(
            "SELECT 1 FROM workout_plan WHERE date = ?", (workout["date"],)
        ).fetchone()
        if exists:
            result["skipped"] += 1
            continue
        conn.execute(
            "INSERT INTO workout_plan (date, day_type, session_type, description, "
            "prescribed_km, target_pace, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                workout["date"],
                workout.get("day_type"),
                workout["session_type"],
                workout.get("description"),
                workout.get("prescribed_km"),
                workout.get("target_pace"),
                workout.get("notes"),
            ),
        )
        result["workouts"] += 1
    conn.commit()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the training calendar from YAML")
    parser.add_argument("plan_file", help="path to your seed_plan.yaml")
    parser.add_argument("--db", default="trainer_data.db")
    args = parser.parse_args()

    plan = yaml.safe_load(Path(args.plan_file).read_text(encoding="utf-8"))
    conn = init_db(args.db)
    result = seed_plan(conn, plan)
    print(
        f"Seeded: {result['phases']} phases, {result['workouts']} workouts "
        f"({result['skipped']} dates already present — idempotent)"
    )


if __name__ == "__main__":
    main()
