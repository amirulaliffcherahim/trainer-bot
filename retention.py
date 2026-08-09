"""Retention — Sunday recap push, milestones, streaks, silence checks.

Everything here is deterministic; the recap reads weekly rollups computed
from verified logs. No guilt — silence checks are gentle re-entry offers.
"""

from __future__ import annotations

from datetime import date, timedelta

from db import compute_weekly_rollup, store_weekly_rollup

MONTH_MILESTONE_KM = 50.0
SILENCE_THRESHOLD_DAYS = 3


def streak_days(conn, user_id: int, today: date) -> int:
    """Consecutive days with a log, ending today (or yesterday if today is
    still unlogged — logging today keeps the streak alive)."""
    logged = {
        row["date"]
        for row in conn.execute(
            "SELECT date FROM daily_logs WHERE user_id = ?", (user_id,)
        )
    }
    cursor = today if today.isoformat() in logged else today - timedelta(days=1)
    streak = 0
    while cursor.isoformat() in logged:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def month_km(conn, user_id: int, today: date) -> float:
    month = today.strftime("%Y-%m")
    row = conn.execute(
        "SELECT COALESCE(SUM(distance_km), 0) AS km FROM daily_logs "
        "WHERE user_id = ? AND date LIKE ? AND completed = 1",
        (user_id, f"{month}%"),
    ).fetchone()
    return round(float(row["km"]), 2)


def days_since_last_log(conn, user_id: int, today: date) -> int | None:
    row = conn.execute(
        "SELECT MAX(date) AS last FROM daily_logs WHERE user_id = ?", (user_id,)
    ).fetchone()
    if not row["last"]:
        return None
    return (today - date.fromisoformat(row["last"])).days


def sunday_recap(
    conn,
    user_id: int,
    *,
    week_start: str,
    today: date | None = None,
    challenge=None,
) -> str:
    """The Sunday push: rollup + streak + month progress + challenge."""
    today = today or date.today()
    rollup = compute_weekly_rollup(conn, user_id, week_start)
    store_weekly_rollup(conn, week_start, rollup)

    streak = streak_days(conn, user_id, today)
    month_total = month_km(conn, user_id, today)

    lines = ["📊 Sunday recap:"]
    lines.append(
        f"• Volume: {rollup['volume_km']} km · completed sessions: "
        f"{rollup['completed_sessions']}"
    )
    lines.append(
        f"• Avg RPE: {rollup['avg_rpe'] if rollup['avg_rpe'] is not None else 'n/a'} · "
        f"fatigue: {rollup['avg_fatigue'] if rollup['avg_fatigue'] is not None else 'n/a'}"
    )
    if rollup["long_run_km"]:
        lines.append(f"• Longest run: {rollup['long_run_km']} km")
    if rollup["weight_trend"] is not None:
        lines.append(f"• Weight trend: {rollup['weight_trend']:+.2f} kg")
    lines.append(f"• Streak: {streak} day{'s' if streak != 1 else ''} · month total: {month_total} km")
    if month_total >= MONTH_MILESTONE_KM:
        lines.append(f"🎉 {month_total:.0f} km this month — milestone!")
    if challenge is not None:
        lines.append(
            f"🏆 This week's challenge: {challenge.title} — {challenge.description}"
        )
    return "\n".join(lines)


def silence_nudge(
    conn,
    user_id: int,
    *,
    today: date,
    threshold_days: int = SILENCE_THRESHOLD_DAYS,
) -> str | None:
    """Gentle re-entry offer after ≥3 days without a log. None = no nudge."""
    since = days_since_last_log(conn, user_id, today)
    if since is None or since < threshold_days:
        return None
    return (
        f"Quiet for {since} days — no judgment, just checking in. "
        "One tap re-opens your plan: /log"
    )
