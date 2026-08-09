"""Scheduler — proactive notifications.

Wires the Phase 6 suggestion engine and retention pushes into production:

- run reminders: fires at RUN_REMIND_TIME on days with a scheduled session
- Sunday recap: 09:00 Sunday
- suggestion pushes: hourly during the day, capped by anti-nag rules

All decision logic is pure and tested; PTB jobs (register_jobs) are thin
adapters. Dedup via sent_notifications — every push is sent at most once
per (type, day). Per-type toggles via notification_prefs (/notify).
"""

from __future__ import annotations

import datetime as dt
import logging

import guardrails
import retention
import suggest
import workouts
from facts import compute_facts
from db import get_recent_history

log = logging.getLogger(__name__)

REMIND_CHECK_INTERVAL = 60  # seconds between reminder checks
SUGGESTION_INTERVAL = 3600  # hourly
RECAP_TIME = dt.time(9, 0)

# In-process persistence for /mute and dismissals (survives within the
# process lifetime; a DB-backed store is a later hardening step).
DEDUP = suggest.DismissalDedup()
MUTE = suggest.MuteState()


# --- prefs & dedup ---------------------------------------------------------


def prefs(conn, user_id: int) -> dict:
    row = conn.execute(
        "SELECT * FROM notification_prefs WHERE user_id = ?", (user_id,)
    ).fetchone()
    if row is None:
        return {"run_reminders": True, "recap": True, "suggestions": True}
    return {
        "run_reminders": bool(row["run_reminders"]),
        "recap": bool(row["recap"]),
        "suggestions": bool(row["suggestions"]),
    }


def set_pref(conn, user_id: int, key: str, enabled: bool) -> None:
    if key not in ("run_reminders", "recap", "suggestions"):
        raise ValueError(f"unknown pref: {key}")
    conn.execute(
        f"INSERT INTO notification_prefs (user_id, {key}) VALUES (?, ?) "
        f"ON CONFLICT(user_id) DO UPDATE SET {key} = excluded.{key}",
        (user_id, 1 if enabled else 0),
    )
    conn.commit()


def has_sent(conn, notification_type: str, user_id: int, date_iso: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sent_notifications WHERE type = ? AND user_id = ? AND date = ?",
        (notification_type, user_id, date_iso),
    ).fetchone()
    return row is not None


def mark_sent(conn, notification_type: str, user_id: int, date_iso: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO sent_notifications (type, date, user_id) VALUES (?, ?, ?)",
        (notification_type, date_iso, user_id),
    )
    conn.commit()


# --- decision logic (pure, tested) -----------------------------------------


def due_run_reminder(
    conn,
    user_id: int,
    *,
    today_iso: str,
    now: dt.time,
    remind_time: dt.time,
    pref: bool = True,
    already_sent: bool = False,
) -> dict | None:
    """Today's scheduled session when the reminder window has arrived."""
    if not pref or already_sent or now < remind_time:
        return None
    row = conn.execute(
        "SELECT * FROM workout_plan WHERE date = ?", (today_iso,)
    ).fetchone()
    return dict(row) if row else None


def due_sunday_recap(
    conn,
    user_id: int,
    *,
    today: dt.date,
    pref: bool = True,
    already_sent: bool = False,
) -> str | None:
    if not pref or already_sent or today.weekday() != 6:  # Sunday
        return None
    week_start = today - dt.timedelta(days=6)  # Monday of this week
    return retention.sunday_recap(
        conn, user_id, week_start=week_start.isoformat(), today=today
    )


def collect_trigger_inputs(conn, user_id: int, today: dt.date) -> dict:
    """All code-computed inputs for the 10 suggestion triggers."""
    phase = workouts.get_phase(conn, today.isoformat())
    phase_name = phase["phase_name"] if phase else "base"

    facts = compute_facts(get_recent_history(conn, user_id), today=today)

    verified_count = conn.execute(
        "SELECT COUNT(*) AS n FROM daily_logs WHERE user_id = ? AND verified = 1",
        (user_id,),
    ).fetchone()["n"]

    pace_trend_pct = 0.0
    if facts.pace_avg_last3_sec_km and facts.pace_avg_prev3_sec_km:
        pace_trend_pct = (
            (facts.pace_avg_prev3_sec_km - facts.pace_avg_last3_sec_km)
            / facts.pace_avg_prev3_sec_km
            * 100
        )

    rollup_rows = conn.execute(
        "SELECT * FROM weekly_rollups ORDER BY week_start DESC LIMIT 3"
    ).fetchall()
    fatigue_series = [
        float(r["avg_fatigue"]) for r in rollup_rows if r["avg_fatigue"] is not None
    ]
    spike_pct = 0.0
    if len(rollup_rows) >= 2 and rollup_rows[0]["volume_km"] and rollup_rows[1]["volume_km"]:
        prev = float(rollup_rows[1]["volume_km"])
        if prev > 0:
            spike_pct = (float(rollup_rows[0]["volume_km"]) - prev) / prev * 100

    today_row = workouts.get_workout(conn, today.isoformat())
    has_quality = bool(
        today_row and "tempo" in (today_row.get("session_type") or "")
    )

    symptom_counts: dict[str, int] = {}
    since = (today - dt.timedelta(days=14)).isoformat()
    for row in conn.execute(
        "SELECT user_input FROM daily_logs WHERE user_id = ? AND date >= ?",
        (user_id, since),
    ):
        text = (row["user_input"] or "").lower()
        for keyword in guardrails.SYMPTOM_KEYWORDS:
            if keyword in text:
                symptom_counts[keyword] = symptom_counts.get(keyword, 0) + 1

    rain = False
    weather_window = (today - dt.timedelta(days=2)).isoformat()
    for row in conn.execute(
        "SELECT user_input FROM daily_logs WHERE user_id = ? AND date >= ?",
        (user_id, weather_window),
    ):
        text = (row["user_input"] or "").lower()
        if any(w in text for w in ("hujan", "rain", "panas", "hot")):
            rain = rain or any(w in text for w in ("hujan", "rain"))

    return {
        "phase_name": phase_name,
        "week_start": (today - dt.timedelta(days=today.weekday())).isoformat(),
        "verified_count": verified_count,
        "pace_trend_pct": round(pace_trend_pct, 1),
        "fatigue_series": fatigue_series,
        "has_quality_today": has_quality,
        "symptom_counts": symptom_counts,
        "month_km": retention.month_km(conn, user_id, today),
        "streak_days": retention.streak_days(conn, user_id, today),
        "missed_sessions": 0,  # placeholder: needs plan-vs-done comparison (Phase 0 seed)
        "volume_spike_pct": round(spike_pct, 1),
        "days_since_last_log": retention.days_since_last_log(conn, user_id, today),
        "days_to_phase_change": (
            (dt.date.fromisoformat(phase["end_date"]) - today).days if phase else 99
        ),
        "week_of_year": today.isocalendar().week,
        "rain": rain,
    }


# --- PTB jobs --------------------------------------------------------------


def _single_user(settings) -> int:
    """The bot is single-user; the first allowlisted id receives pushes."""
    return next(iter(settings.allowed_user_ids))


async def run_reminder_job(context) -> None:
    conn = context.bot_data["conn"]
    settings = context.bot_data["settings"]
    user_id = _single_user(settings)
    today = dt.date.today()
    today_iso = today.isoformat()

    remind = dt.datetime.strptime(settings.run_remind_time, "%H:%M").time()
    workout = due_run_reminder(
        conn,
        user_id,
        today_iso=today_iso,
        now=dt.datetime.now().time(),
        remind_time=remind,
        pref=prefs(conn, user_id)["run_reminders"],
        already_sent=has_sent(conn, "run_reminder", user_id, today_iso),
    )
    if workout is None:
        return
    mark_sent(conn, "run_reminder", user_id, today_iso)
    text = (
        f"🏃 Run time! Today ({today_iso}): {workout['session_type']}"
    )
    parts = []
    if workout.get("prescribed_km"):
        parts.append(f"{workout['prescribed_km']} km")
    if workout.get("target_pace"):
        parts.append(f"@{workout['target_pace']}")
    if parts:
        text += " · " + " · ".join(parts)
    if workout.get("notes"):
        text += f"\n{workout['notes']}"
    await context.bot.send_message(chat_id=user_id, text=text)


async def sunday_recap_job(context) -> None:
    conn = context.bot_data["conn"]
    settings = context.bot_data["settings"]
    user_id = _single_user(settings)
    today = dt.date.today()
    today_iso = today.isoformat()
    recap = due_sunday_recap(
        conn,
        user_id,
        today=today,
        pref=prefs(conn, user_id)["recap"],
        already_sent=has_sent(conn, "recap", user_id, today_iso),
    )
    if recap is None:
        return
    mark_sent(conn, "recap", user_id, today_iso)
    await context.bot.send_message(chat_id=user_id, text=recap)


async def suggestion_job(context) -> None:
    conn = context.bot_data["conn"]
    settings = context.bot_data["settings"]
    user_id = _single_user(settings)
    today = dt.date.today()
    if not prefs(conn, user_id)["suggestions"]:
        return
    now = dt.datetime.now()
    if suggest.in_quiet_hours(now):
        return

    inputs = collect_trigger_inputs(conn, user_id, today)
    triggers = [
        suggest.trigger_weekly_challenge(conn, inputs["week_start"], inputs["phase_name"]),
        suggest.trigger_prediction_update(inputs["verified_count"], inputs["pace_trend_pct"]),
        suggest.trigger_recovery_nudge(inputs["fatigue_series"], inputs["has_quality_today"]),
        suggest.trigger_injury_watch(inputs["symptom_counts"]),
        suggest.trigger_session_adjustment(rain=inputs.get("rain", False)),
        suggest.trigger_milestone(inputs["month_km"], inputs["streak_days"]),
        suggest.trigger_plan_drift(inputs["missed_sessions"], inputs["volume_spike_pct"]),
        suggest.trigger_phase_boundary(inputs["days_to_phase_change"]),
        suggest.trigger_silence_check(inputs["days_since_last_log"] or 0),
        suggest.trigger_form_check(inputs["week_of_year"], None),
    ]
    dismissed_types = set(DEDUP._dismissed.get(user_id, {}))
    pushes = suggest.evaluate_suggestions(
        triggers=triggers,
        now=now,
        phase_name=inputs["phase_name"],
        budget=suggest.PushBudget(),
        muted=MUTE.muted(user_id),
        dismissed_types=dismissed_types,
    )
    for push in pushes:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"{push.message}\n\n👉 {push.action}: {push.command}",
        )


def register_jobs(app) -> None:
    """Attach scheduled jobs to the PTB application."""
    if app.job_queue is None:
        log.warning("No job queue available — notifications disabled")
        return
    app.job_queue.run_repeating(run_reminder_job, interval=REMIND_CHECK_INTERVAL, first=10)
    app.job_queue.run_daily(sunday_recap_job, time=RECAP_TIME, days=(6,))
    app.job_queue.run_repeating(suggestion_job, interval=SUGGESTION_INTERVAL, first=300)
    log.info("Scheduled jobs registered: run reminder, Sunday recap, suggestions")
