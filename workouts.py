"""Phase-aware training queries — /today = training_phases × workout_plan.

The phase calendar and week-by-week program are seed data (provided by the
deployer for their own event — Phase 0). These functions read them; they
never hardcode dates or targets.
"""

from __future__ import annotations

import re

_PACE_RE = re.compile(r"(\d{1,2}):(\d{2})")


def parse_pace_sec_km(value: str | None) -> float | None:
    """'7:10' / '7:10/km' / '7:10 min/km' → 430.0 sec/km. None if unparseable."""
    if not value:
        return None
    match = _PACE_RE.search(value.strip())
    if not match:
        return None
    return int(match.group(1)) * 60 + int(match.group(2))


def get_phase(conn, date_iso: str) -> dict | None:
    """The training_phases row spanning date_iso, or None."""
    row = conn.execute(
        "SELECT * FROM training_phases WHERE start_date <= ? AND end_date >= ? "
        "ORDER BY start_date DESC LIMIT 1",
        (date_iso, date_iso),
    ).fetchone()
    return dict(row) if row else None


def get_workout(conn, date_iso: str) -> dict | None:
    """The workout_plan row for date_iso, or None."""
    row = conn.execute(
        "SELECT * FROM workout_plan WHERE date = ? LIMIT 1", (date_iso,)
    ).fetchone()
    return dict(row) if row else None


def format_today(
    date_iso: str,
    phase: dict | None,
    workout: dict | None,
    *,
    target_pace: str | None = None,
) -> str:
    """Render the /today reply. Graceful when seed data is missing."""
    lines: list[str] = []

    if phase is None:
        lines.append("📅 Training calendar not seeded yet (Phase 0).")
    else:
        lines.append(
            f"📅 Phase: **{phase['phase_name']}** "
            f"({phase['start_date']} → {phase['end_date']})"
        )
        if phase.get("focus"):
            lines.append(f"Focus: {phase['focus']}")

    if workout is None:
        lines.append("🏋️ No workout scheduled for today — rest or mobility.")
    else:
        lines.append(
            f"🏃 Today ({date_iso}): **{workout['session_type']}**"
        )
        if workout.get("description"):
            lines.append(workout["description"])
        parts = []
        if workout.get("prescribed_km"):
            parts.append(f"{workout['prescribed_km']} km")
        if workout.get("target_pace"):
            parts.append(f"@{workout['target_pace']}")
        if parts:
            lines.append(" · ".join(parts))
        if workout.get("notes"):
            lines.append(f"Note: {workout['notes']}")

    if target_pace:
        lines.append(f"🎯 Race target: {target_pace}")

    return "\n".join(lines)
