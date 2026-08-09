"""bot.py — Telegram wiring.

Security order (every handler):
1. allowlist gate — strangers are SILENTLY dropped before any processing
   (no LLM, no OCR, no DB access, no error detail)
2. 1 msg/sec debounce per user
3. then the real work

Text flow: guardrails → extraction → computed facts → per-persona retrieval
→ 4 concurrent persona passes → editor merge → validation → store.
Photo flow: Strava pipeline (ocr → parse → math check → echo-confirm →
verified=1 on confirmation).

Button callback_data uses short draft refs (cf:<id> / cffix:<id>:<field>) —
Telegram's 64-byte limit is never approached.
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
import time
from datetime import date, timedelta
from pathlib import Path

from telegram import InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
import db
import extract
import facts
import guardrails
import ocr
import retrieval
import scheduler
import strava
import validate
import workouts
from config import Settings
from llm_client import AllModelsFailed, LLMClient
from personas import load_personas
from synthesize import generate_reply

log = logging.getLogger(__name__)

PERSONAS = load_personas()
_EMBEDDER = None


def _get_embedder():
    global _EMBEDDER
    if _EMBEDDER is None:
        from retrieval import SentenceTransformerEmbedder

        _EMBEDDER = SentenceTransformerEmbedder()
    return _EMBEDDER


def _render_kb(hits: list) -> str:
    return "\n".join(
        f"- [SOURCE: {h.source}] {h.title}\n  {h.content[:400]}"
        for h in hits
    )


# --- auth & abuse guards -------------------------------------------------


def authorize(user_id: int | None, allowed: set[int]) -> bool:
    """The allowlist gate — THE security boundary of the bot."""
    return user_id is not None and user_id in allowed


class Debouncer:
    """1 message per second per user."""

    def __init__(self, min_interval: float = 1.0) -> None:
        self.min_interval = min_interval
        self._last: dict[int, float] = {}

    def allow(self, user_id: int, now: float | None = None) -> bool:
        now = now if now is not None else time.monotonic()
        last = self._last.get(user_id)
        if last is not None and now - last < self.min_interval:
            return False
        self._last[user_id] = now
        return True


class DraftStore:
    """Pending Strava confirmations, keyed by short draft ids + per-user
    fix-state. TTL keeps stale drafts from piling up."""

    def __init__(self, ttl: float = 900.0) -> None:
        self.ttl = ttl
        self._drafts: dict[str, tuple[float, strava.StravaRead]] = {}
        self._fix: dict[int, tuple[str, str]] = {}  # user_id → (draft_id, field)

    def put(self, read: strava.StravaRead) -> str:
        draft_id = f"{int(time.time() * 1000):x}{len(self._drafts):x}"
        self._drafts[draft_id] = (time.monotonic(), read)
        return draft_id

    def get(self, draft_id: str) -> strava.StravaRead | None:
        entry = self._drafts.get(draft_id)
        if entry is None:
            return None
        created, read = entry
        if time.monotonic() - created > self.ttl:
            self._drafts.pop(draft_id, None)
            return None
        return read

    def pop(self, draft_id: str) -> strava.StravaRead | None:
        read = self.get(draft_id)
        if read is not None:
            self._drafts.pop(draft_id, None)
        return read

    def set_fix(self, user_id: int, draft_id: str, field: str) -> None:
        self._fix[user_id] = (draft_id, field)

    def pop_fix(self, user_id: int) -> tuple[str, str] | None:
        return self._fix.pop(user_id, None)


DEBOUNCER = Debouncer()
DRAFTS = DraftStore()


def _gate(update: Update, settings: Settings) -> bool:
    """Silent reject for strangers; debounce for everyone. False → stop."""
    user = update.effective_user
    if not authorize(user.id if user else None, settings.allowed_user_ids):
        return False
    if user and not DEBOUNCER.allow(user.id):
        return False
    return True


# --- commands ------------------------------------------------------------


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.bot_data["settings"]
    if not _gate(update, settings):
        return
    phase = workouts.get_phase(context.bot_data["conn"], date.today().isoformat())
    intro = (
        "Hey! I'm your coach — running, strength, mobility, and keeping you "
        "in one piece. Four perspectives, one brain, zero lecture."
    )
    if phase:
        intro += f"\n\nRight now you're in {phase['phase_name']}."
    intro += (
        "\n\nJust chat like you would with any coach: log a run "
        "(\"easy 5k, RPE 6\"), send a Strava screenshot, ask why anything "
        "works. If you ever want shortcuts, /help has them."
    )
    await update.message.reply_text(intro)


async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.bot_data["settings"]
    if not _gate(update, settings):
        return
    conn = context.bot_data["conn"]
    user_id = update.effective_user.id
    today = date.today().isoformat()
    phase = workouts.get_phase(conn, today)
    workout = workouts.get_workout(conn, today)
    row = conn.execute(
        "SELECT target_pace FROM athlete_profile WHERE user_id = ?", (user_id,)
    ).fetchone()
    target = row["target_pace"] if row and row["target_pace"] else None
    await update.message.reply_text(
        workouts.format_today(today, phase, workout, target_pace=target)
    )


async def cmd_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.bot_data["settings"]
    if not _gate(update, settings):
        return
    conn = context.bot_data["conn"]
    user_id = update.effective_user.id
    rows = conn.execute(
        "SELECT * FROM weekly_rollups ORDER BY week_start DESC LIMIT 2"
    ).fetchall()
    if not rows:
        await update.message.reply_text("No weekly rollups yet — log some sessions first.")
        return
    lines = ["📊 Weekly summary:"]
    for row in rows:
        lines.append(
            f"• Week {row['week_start']}: {row['volume_km']} km, "
            f"RPE {row['avg_rpe'] if row['avg_rpe'] is not None else 'n/a'}, "
            f"fatigue {row['avg_fatigue'] if row['avg_fatigue'] is not None else 'n/a'}, "
            f"{row['completed_sessions']} sessions"
        )
    await update.message.reply_text("\n".join(lines))


async def cmd_log(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.bot_data["settings"]
    if not _gate(update, settings):
        return
    await update.message.reply_text(
        "Log a session in plain words, e.g.:\n"
        "\"easy 5km, RPE 6, legs tired\"\n"
        "or send a Strava screenshot with a caption."
    )


TIME_RE_3 = re.compile(r"^(\d{1,2}):([0-5]\d):([0-5]\d)$")  # H:MM:SS
TIME_RE_2 = re.compile(r"^(\d{1,2}):([0-5]\d)$")  # M:SS (race times < 100 min)
HALF_MARATHON_KM = 21.0975


def parse_target_arg(text: str) -> tuple[str, int]:
    """'/target <race name> <H:MM:SS | M:SS>' → (race_name, target_seconds)."""
    parts = text.strip().split()
    if len(parts) < 2:
        raise ValueError("usage: /target <race name> <H:MM:SS> — e.g. /target SELMAR Half Marathon 2:30:00")
    time_token = parts[-1]
    match = TIME_RE_3.match(time_token)
    if match:
        total = int(match.group(1)) * 3600 + int(match.group(2)) * 60 + int(match.group(3))
    else:
        match = TIME_RE_2.match(time_token)
        if not match:
            raise ValueError(f"target time must be M:SS or H:MM:SS, got {time_token!r}")
        total = int(match.group(1)) * 60 + int(match.group(2))
    if total <= 0:
        raise ValueError("target time must be positive")
    return " ".join(parts[:-1]), total


_WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


def resolve_log_date(raw: str | None, today: date) -> str | None:
    """Normalize a date mention to ISO YYYY-MM-DD. None when unparseable.

    Accepts: ISO dates, today/yesterday, 'N days ago', 'last <weekday>'.
    """
    if not raw:
        return None
    text = raw.strip().lower()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
        return text
    if text == "today":
        return today.isoformat()
    if text == "yesterday":
        return (today - timedelta(days=1)).isoformat()
    match = re.match(r"^(\d+)\s+days?\s+ago$", text)
    if match:
        return (today - timedelta(days=int(match.group(1)))).isoformat()
    match = re.match(r"^last\s+(" + "|".join(_WEEKDAYS) + r")$", text)
    if match:
        target = _WEEKDAYS[match.group(1)]
        delta = (today.weekday() - target) % 7
        if delta == 0:
            delta = 7
        return (today - timedelta(days=delta)).isoformat()
    return None


PROFILE_KEYS = {
    "height": ("height_cm", 100, 250),
    "weight": ("weight_kg", 30, 200),
    "age": ("age", 10, 100),
    "vo2": ("vo2_max", 20, 90),
    "max_bpm": ("max_bpm", 80, 250),
    "resting_bpm": ("resting_bpm", 30, 150),
}
NA_VALUES = {"n/a", "na", "-", "unknown", "none"}


def parse_profile_arg(tokens: list[str]) -> dict[str, object]:
    """['height=175', 'age=28', 'vo2=n/a'] → {"height_cm": 175.0, "age": 28, "vo2_max": None}.
    'n/a' and friends → None (NULL). Unknown keys / bad values raise ValueError."""
    out: dict[str, object] = {}
    for token in tokens:
        if "=" not in token:
            raise ValueError(f"expected key=value, got {token!r}")
        key, _, raw = token.partition("=")
        key = key.strip().lower()
        if key not in PROFILE_KEYS:
            raise ValueError(f"unknown field {key!r} — use: {', '.join(sorted(PROFILE_KEYS))}")
        column, low, high = PROFILE_KEYS[key]
        value = raw.strip()
        if value.lower() in NA_VALUES or value == "":
            out[column] = None
            continue
        try:
            parsed = float(value) if column in ("height_cm", "weight_kg", "vo2_max") else int(float(value))
        except ValueError as exc:
            raise ValueError(f"{key} value {value!r} is not a number")
        if not (low <= parsed <= high):
            raise ValueError(f"{key} must be {low}-{high}, got {value}")
        out[column] = parsed
    return out


PROFILE_KEYWORD_RE = re.compile(
    r"\b(heights?|weight|kg|cm|vo2|bpm|heart\s*rate|resting|age|target|race|goal)\b",
    re.IGNORECASE,
)

EXPLAIN_RE = re.compile(
    r"\b(explain|why|how does|how come|what'?s the reason|tell me more|elaborate|go deeper|kenapa|macam mana|bagaimana)\b",
    re.IGNORECASE,
)


def apply_profile_extraction(
    conn, user_id: int, profile: "extract.ProfileExtraction", today: date
) -> str | None:
    """Merge chat-captured profile fields into athlete_profile. Weight also
    becomes today's daily log entry. Returns the acknowledgment or None."""
    updates = profile.model_dump(exclude_none=True)
    target_race = updates.pop("target_race", None)
    target_time = updates.pop("target_time_raw", None)
    if not updates and not target_race and not target_time:
        return None

    if conn.execute(
        "SELECT 1 FROM athlete_profile WHERE user_id = ?", (user_id,)
    ).fetchone() is None:
        conn.execute("INSERT INTO athlete_profile (user_id) VALUES (?)", (user_id,))

    sets: list[str] = []
    values: list[object] = []
    for column, value in updates.items():
        sets.append(f"{column} = ?")
        values.append(value)
    if target_race:
        sets.append("target_race = ?")
        values.append(target_race)
    pace_text = None
    if target_time:
        _, target_sec = parse_target_arg(f"x {target_time}")
        pace_sec_km = target_sec / HALF_MARATHON_KM
        pace_text = f"{int(pace_sec_km // 60)}:{int(pace_sec_km % 60):02d} min/km"
        sets.append("target_pace = ?")
        values.append(pace_text)
    conn.execute(
        f"UPDATE athlete_profile SET {', '.join(sets)}, updated_at = datetime('now') "
        "WHERE user_id = ?",
        [*values, user_id],
    )
    if profile.weight_kg is not None:
        db.save_log(
            conn,
            date=today.isoformat(),
            user_id=user_id,
            user_input="weight",
            ai_response="weight logged",
            weight_kg=profile.weight_kg,
            completed=0,
        )
    conn.commit()

    parts: list[str] = []
    if profile.height_cm is not None:
        parts.append(f"height {profile.height_cm:g} cm")
    if profile.weight_kg is not None:
        parts.append(f"weight {profile.weight_kg:g} kg")
    if profile.age is not None:
        parts.append(f"age {profile.age} y")
    if profile.vo2_max is not None:
        parts.append(f"VO2 max {profile.vo2_max:g}")
    if profile.max_bpm is not None:
        parts.append(f"max HR {profile.max_bpm} bpm")
    if profile.resting_bpm is not None:
        parts.append(f"resting HR {profile.resting_bpm} bpm")
    if target_race:
        parts.append(f"target {target_race} @ {pace_text or 'see /target'}")
    return "Got it — " + ", ".join(parts) if parts else None


def profile_snapshot(conn, user_id: int) -> str:
    """One-line profile summary injected into every persona prompt."""
    row = conn.execute("SELECT * FROM athlete_profile WHERE user_id = ?", (user_id,)).fetchone()
    if row is None:
        return "## Profile\nNo profile data yet — /profile to set it."

    def fmt(value, suffix=""):
        if value is None:
            return "n/a"
        if isinstance(value, float):
            value = f"{value:g}"
        return f"{value}{suffix}"

    parts = [
        f"height {fmt(row['height_cm'], ' cm')}",
        f"weight {fmt(row['weight_kg'], ' kg')}",
        f"age {fmt(row['age'], ' y')}",
        f"VO2 max {fmt(row['vo2_max'])}",
        f"max HR {fmt(row['max_bpm'], ' bpm')}",
        f"resting HR {fmt(row['resting_bpm'], ' bpm')}",
    ]
    if row["target_race"]:
        parts.append(f"target {row['target_race']} @ {row['target_pace']}")
    return "## Profile (athlete data — treat as facts)\n" + ", ".join(parts)


async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.bot_data["settings"]
    if not _gate(update, settings):
        return
    conn = context.bot_data["conn"]
    user_id = update.effective_user.id
    args = context.args or []
    if not args:
        await update.message.reply_text(
            profile_snapshot(conn, user_id)
            + "\n\nUpdate: /profile height=175 weight=56 age=28 vo2=n/a max_bpm=190 resting_bpm=55"
            + "\nAny field accepts n/a to clear it."
        )
        return
    try:
        updates = parse_profile_arg(args)
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return
    sets = ", ".join(f"{col} = ?" for col in updates)
    conn.execute(
        f"INSERT INTO athlete_profile (user_id, updated_at) VALUES (?, datetime('now')) "
        f"ON CONFLICT(user_id) DO UPDATE SET {sets}, updated_at = datetime('now')",
        [user_id, *updates.values()],
    )
    conn.commit()
    await update.message.reply_text(
        "✅ Profile updated:\n" + profile_snapshot(conn, user_id)
    )


async def cmd_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.bot_data["settings"]
    if not _gate(update, settings):
        return
    conn = context.bot_data["conn"]
    user_id = update.effective_user.id
    arg = " ".join(context.args or [])
    if not arg:
        row = conn.execute(
            "SELECT target_race, target_pace FROM athlete_profile WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if row and row["target_race"]:
            await update.message.reply_text(
                f"🎯 {row['target_race']} — target pace {row['target_pace']}\n"
                "Update: /target <race name> <H:MM:SS>"
            )
        else:
            await update.message.reply_text(
                "No target set. Usage: /target <race name> <H:MM:SS>\n"
                "e.g. /target SELMAR Half Marathon 2:30:00"
            )
        return
    try:
        race_name, target_sec = parse_target_arg(arg)
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return
    pace_sec_km = target_sec / HALF_MARATHON_KM
    pace_text = f"{int(pace_sec_km // 60)}:{int(pace_sec_km % 60):02d} min/km"
    conn.execute(
        "INSERT INTO athlete_profile (user_id, target_race, target_pace, updated_at) "
        "VALUES (?, ?, ?, datetime('now')) "
        "ON CONFLICT(user_id) DO UPDATE SET target_race = excluded.target_race, "
        "target_pace = excluded.target_pace, updated_at = datetime('now')",
        (user_id, race_name, pace_text),
    )
    conn.commit()
    await update.message.reply_text(
        f"🎯 Target set: **{race_name}** in {arg.split()[-1]} ≈ {pace_text}.\n"
        "All pace advice now references this goal."
    )


async def cmd_weight(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.bot_data["settings"]
    if not _gate(update, settings):
        return
    conn = context.bot_data["conn"]
    user_id = update.effective_user.id
    args = context.args
    if not args:
        row = conn.execute(
            "SELECT weight_kg FROM athlete_profile WHERE user_id = ?", (user_id,)
        ).fetchone()
        current = row["weight_kg"] if row else None
        await update.message.reply_text(
            f"Current weight: {current} kg. Update: /weight 55.4"
        )
        return
    try:
        weight = float(args[0])
    except ValueError:
        await update.message.reply_text("Usage: /weight 55.4")
        return
    if not 30 <= weight <= 200:
        await update.message.reply_text("Weight must be 30–200 kg.")
        return
    conn.execute(
        "INSERT INTO athlete_profile (user_id, weight_kg, updated_at) "
        "VALUES (?, ?, datetime('now')) "
        "ON CONFLICT(user_id) DO UPDATE SET weight_kg = excluded.weight_kg, "
        "updated_at = datetime('now')",
        (user_id, weight),
    )
    # Also log today's weight as a daily entry so weekly weight trends work.
    db.save_log(
        conn,
        date=date.today().isoformat(),
        user_id=user_id,
        user_input="weight",
        ai_response="weight logged",
        weight_kg=weight,
        completed=0,
    )
    conn.commit()
    await update.message.reply_text(
        f"Weight updated: {weight} kg ✅ (also recorded in today's history)"
    )


async def cmd_phase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.bot_data["settings"]
    if not _gate(update, settings):
        return
    conn = context.bot_data["conn"]
    today = date.today().isoformat()
    phase = workouts.get_phase(conn, today)
    await update.message.reply_text(
        workouts.format_today(today, phase, None)
    )


async def cmd_personas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.bot_data["settings"]
    if not _gate(update, settings):
        return
    await update.message.reply_text(
        "🧠 The four experts behind every answer:\n"
        "1. **Runner coach** — pacing, volume, phases, race strategy\n"
        "2. **Calisthenics coach** — strength, progressions\n"
        "3. **Mobility coach** — flexibility, routines\n"
        "4. **Physio** — injuries, red flags (safety veto — always wins)"
    )


# --- message flows --------------------------------------------------------


async def cmd_notify(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.bot_data["settings"]
    if not _gate(update, settings):
        return
    conn = context.bot_data["conn"]
    user_id = update.effective_user.id
    current = scheduler.prefs(conn, user_id)
    from telegram import InlineKeyboardButton

    def toggle(key: str, label: str) -> InlineKeyboardButton:
        state = "✅ ON" if current[key] else "⛔ OFF"
        return InlineKeyboardButton(f"{label}: {state}", callback_data=f"nt:{key}")

    keyboard = InlineKeyboardMarkup(
        [[toggle("run_reminders", "Run reminders")],
         [toggle("recap", "Sunday recap")],
         [toggle("suggestions", "Coach suggestions")]]
    )
    await update.message.reply_text(
        "🔔 Notifications — tap to toggle:\n"
        "• Run reminders: daily at the configured time when a session is scheduled\n"
        "• Sunday recap: weekly summary push\n"
        "• Coach suggestions: proactive tips (max 2/day, quiet at night)",
        reply_markup=keyboard,
    )


async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.bot_data["settings"]
    if not _gate(update, settings):
        return
    user_id = update.effective_user.id
    arg = (context.args[0] if context.args else "").lower()
    if arg == "1d":
        scheduler.MUTE.mute(user_id, 86400)
        await update.message.reply_text("🔕 Notifications muted for 1 day. /mute off to unmute.")
    elif arg == "1w":
        scheduler.MUTE.mute(user_id, 7 * 86400)
        await update.message.reply_text("🔕 Notifications muted for 1 week. /mute off to unmute.")
    else:
        scheduler.MUTE.mute(user_id, 0)
        await update.message.reply_text(
            "🔔 Unmuted. Usage: /mute 1d | /mute 1w | /mute off"
        )


HELP_TEXT = (
    "🤖 **Trainer bot commands**\n\n"
    "• /start — introduction & current phase\n"
    "• /today — today's scheduled session (needs seeded calendar)\n"
    "• /summary — weekly rollup (volume, RPE, fatigue)\n"
    "• /log — how to log: plain text (\"easy 5km, RPE 6\") or a Strava "
    "screenshot; backdate with \"on 2026-07-28\" / \"yesterday\" / \"3 days ago\"\n"
    "• /weight <kg> — update weight (also records today's entry)\n"
    "• /profile [key=value …] — height, weight, age, vo2, max_bpm, "
    "resting_bpm; n/a clears a field\n"
    "• /target <race> <H:MM:SS> — set your event goal (e.g. /target SELMAR Half Marathon 2:30:00)\n"
    "• /phase — current training phase\n"
    "• /personas — the four expert perspectives\n"
    "• /predict — race-time prediction from verified efforts\n"
    "• /notify — toggle run reminders / Sunday recap / suggestions\n"
    "• /mute 1d|1w — silence notifications\n"
    "• /help — this message\n\n"
    "💡 Tip: typing / in Telegram shows this menu."
)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.bot_data["settings"]
    if not _gate(update, settings):
        return
    await update.message.reply_text(HELP_TEXT)


COMMAND_LIST = [
    ("start", "Introduction"),
    ("today", "Today's session"),
    ("summary", "Weekly stats"),
    ("log", "Log a run (text or screenshot)"),
    ("weight", "Update weight"),
    ("profile", "Height / VO2 / age / heart-rate baselines"),
    ("target", "Set event goal"),
    ("predict", "Race-time prediction"),
    ("phase", "Current training phase"),
    ("personas", "The four experts"),
    ("notify", "Notification toggles"),
    ("mute", "Silence notifications"),
    ("help", "Explain commands"),
]


async def _set_commands(app) -> None:
    """Register the / menu (Telegram shows it when the user types '/')."""
    from telegram import BotCommand

    await app.bot.set_my_commands(
        [BotCommand(name, description) for name, description in COMMAND_LIST]
    )


def merge_ack(answer: str, ack: str | None) -> str:
    """Fold the profile acknowledgment into the main reply — one message,
    never two."""
    return f"{ack}\n\n{answer}" if ack else answer


COACH_PRELUDE = (
    "hmm, gimme a bit — coach brain warming up…",
    "one sec, chugging my water first…",
    "hold on, let me look at your numbers…",
    "ok gimme a second, thinking out loud…",
    "one moment, pulling my notes on this…",
    "hmm… lemme think about this one…",
)


def coach_prelude() -> str:
    return random.choice(COACH_PRELUDE)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.bot_data["settings"]
    if not _gate(update, settings):
        return
    conn = context.bot_data["conn"]
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # Pending Strava fix from an echo-confirm?
    pending = DRAFTS.pop_fix(user_id)
    if pending:
        await _apply_fix(update, context, pending, text)
        return

    # 1. Guardrails FIRST — red flags bypass the AI entirely.
    result = guardrails.evaluate_guardrails(text)
    if result.triggered:
        await update.message.reply_text(result.response)
        return

    client: LLMClient = context.bot_data["llm_client"]

    # Coach interjection while the brain works — edited away when the real
    # reply lands, so the chat never shows two messages.
    placeholder = await update.message.reply_text(coach_prelude())

    # 1b. Conversational profile intake — best-effort, silent on failure.
    profile_ack = None
    if PROFILE_KEYWORD_RE.search(text) and re.search(r"\d", text):
        try:
            profile = await extract.extract_profile(client, text)
            profile_ack = apply_profile_extraction(
                conn, user_id, profile, date.today()
            )
        except (extract.ExtractionFailed, AllModelsFailed):
            pass  # profile pass is best-effort

    # 2. Computed facts from real data (code, not AI).
    rows = db.get_recent_history(conn, user_id)
    fb = facts.compute_facts(rows, today=date.today())
    embedder = _get_embedder()

    def retrieval_fn(persona_key: str, message: str) -> str:
        hits = retrieval.retrieve(conn, embedder, persona_key, message)
        return _render_kb(hits)

    try:
        answer, drafts = await generate_reply(
            client,
            PERSONAS,
            facts=fb,
            user_message=text,
            retrieval_fn=retrieval_fn,
            profile_str=profile_snapshot(conn, user_id),
            explain=bool(EXPLAIN_RE.search(text)),
            knowledge_seeking=is_knowledge_seeking(text),
        )
    except AllModelsFailed:
        await placeholder.edit_text(
            "AI's down for a sec — try again in a minute."
        )
        return

    final = merge_ack(answer, profile_ack)
    await placeholder.edit_text(final)

    # 3. Structured logging in the BACKGROUND — the reply never waits for it.
    asyncio.create_task(_store_log_background(client, conn, user_id, text))


async def _store_log_background(
    client: LLMClient,
    conn,
    user_id: int,
    text: str,
) -> None:
    """Background structured logging — never blocks the coaching reply.
    Best-effort: failure drops quietly (the reply already happened)."""
    try:
        extracted = await extract.extract_log(client, text)
    except (extract.ExtractionFailed, AllModelsFailed):
        log.info("background extraction failed — message not structured")
        return
    log_date = (
        resolve_log_date(extracted.date_raw, date.today()) or date.today().isoformat()
    )
    trusted = bool(extracted.distance_km and extracted.moving_time_min)
    db.save_log(
        conn,
        date=log_date,
        user_id=user_id,
        user_input=text,
        ai_response="logged",
        rpe=extracted.rpe,
        fatigue_level=extracted.fatigue_level,
        weight_kg=extracted.weight_kg,
        sleep_hours=extracted.sleep_hours,
        session_type=extracted.session_type,
        distance_km=extracted.distance_km,
        moving_time_min=extracted.moving_time_min,
        completed=1 if extracted.completed else 0,
        verified=1 if trusted else 0,
        model_used=client.last_model_used,
        prompt_version="pipeline-v1",
    )
    if trusted:
        conn.execute(
            "INSERT INTO performance_anchors (date, distance_km, time_sec, source, verified) "
            "VALUES (?, ?, ?, 'chat', 1)",
            (log_date, extracted.distance_km, int(round(extracted.moving_time_min * 60))),
        )
    conn.commit()


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.bot_data["settings"]
    if not _gate(update, settings):
        return
    conn = context.bot_data["conn"]
    user_id = update.effective_user.id
    caption = update.message.caption or ""

    # 1. Guardrails on the caption too.
    result = guardrails.evaluate_guardrails(caption)
    if result.triggered:
        await update.message.reply_text(result.response)
        return

    placeholder = await update.message.reply_text(
        "one sec, squinting at that screenshot…"
    )

    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        image_bytes = bytes(await file.download_as_bytearray())
    except Exception as exc:  # noqa: BLE001 — Telegram errors surface as plain failure
        log.warning("photo download failed: %s", exc)
        await placeholder.edit_text("Couldn't download that image.")
        return

    ocr_text = await asyncio.to_thread(
        ocr.extract_text, image_bytes, vision_api_key=settings.vision_api_key
    )
    if not ocr_text.strip():
        await placeholder.edit_text(
            "No text found in that image. Send a clearer screenshot, or type "
            "distance and time manually."
        )
        return

    client: LLMClient = context.bot_data["llm_client"]
    try:
        read = await strava.process_screenshot(
            client, conn, ocr_text, caption=caption
        )
    except strava.ParseFailed:
        await placeholder.edit_text(
            "Couldn't read the numbers. Please type distance and time manually, "
            "e.g. \"10.42 km, 72:38\"."
        )
        return
    except AllModelsFailed:
        await placeholder.edit_text("AI unavailable — try again in a minute.")
        return

    draft_id = DRAFTS.put(read)
    await placeholder.edit_text(
        strava.build_echo(read), reply_markup=strava.build_confirm_keyboard(draft_id)
    )


async def _apply_fix(
    update: Update, context: ContextTypes.DEFAULT_TYPE, pending: tuple[str, str], value: str
) -> None:
    draft_id, field = pending
    read = DRAFTS.get(draft_id)
    if read is None:
        await update.message.reply_text("That confirmation expired — send the screenshot again.")
        return
    try:
        if field == "distance_km":
            read.fields.distance_km = float(value)
        elif field == "avg_pace":
            read.fields.avg_pace_text = value.strip()
        elif field == "date":
            read.fields.date = value.strip()
        else:
            await update.message.reply_text("Unknown field to fix.")
            return
    except ValueError:
        await update.message.reply_text(f"Couldn't parse '{value}' — try again.")
        return
    # Re-run the math check with the corrected value.
    computed, delta, uncertain = strava.math_check(read.fields)
    read.computed_pace_sec_km = computed
    read.pace_delta_sec_km = delta
    read.uncertain = uncertain
    read.plan_deltas = strava.plan_deltas(read)
    draft_id = DRAFTS.put(read)
    await update.message.reply_text(
        strava.build_echo(read), reply_markup=strava.build_confirm_keyboard(draft_id)
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.bot_data["settings"]
    if not _gate(update, settings):
        return
    query = update.callback_query
    if query is None:
        return
    data = query.data or ""
    await query.answer()

    if data.startswith("cf:"):
        draft_id = data[3:]
        read = DRAFTS.pop(draft_id)
        if read is None:
            await query.edit_message_text("That confirmation expired — send the screenshot again.")
            return
        conn = context.bot_data["conn"]
        log_id = strava.confirm_draft(
            conn, read, user_id=update.effective_user.id,
            caption=(query.message.text if query.message else "") or "",
        )
        await query.edit_message_text(
            f"✅ Logged (verified, id {log_id}).\n{strava.build_echo(read)}"
        )
    elif data.startswith("nt:"):
        key = data[3:]
        conn = context.bot_data["conn"]
        user_id = update.effective_user.id
        current = scheduler.prefs(conn, user_id)
        scheduler.set_pref(conn, user_id, key, not current.get(key, True))
        await query.edit_message_text(
            f"🔔 {key.replace('_', ' ')} toggled to "
            f"{'ON' if scheduler.prefs(conn, user_id)[key] else 'OFF'}."
        )
    elif data.startswith("cffix:"):
        _, draft_id, field = data.split(":", 2)
        DRAFTS.set_fix(update.effective_user.id, draft_id, field)
        await query.edit_message_text(
            f"Send the correct {field.replace('_', ' ')} (e.g. 5.02 for distance, "
            "6:58 for pace, 2026-01-15 for date)."
        )


# --- application ----------------------------------------------------------


def auto_seed(conn, *, kb_root: Path | None = None, embedder=None) -> None:
    """Cold-start seeding: ingest the knowledge base on first start.

    The training calendar/phase seeding is intentionally NOT automated — the
    deployer's event calendar is theirs to provide (dynamic by design);
    /today degrades gracefully until then.
    """
    kb_root = kb_root or Path(__file__).resolve().parent / "knowledge"
    count = conn.execute("SELECT COUNT(*) AS n FROM kb_chunks").fetchone()["n"]
    if count > 0:
        return
    log.info("Knowledge base empty — auto-ingesting %s", kb_root)
    from ingest_kb import ingest_kb

    ingest_kb(conn, embedder or _get_embedder(), kb_root)


def build_application(settings: Settings, *, auto_seed_kb: bool = True) -> Application:
    """Wire handlers, jobs, and cold-start KB seeding.

    Param named auto_seed_kb (not auto_seed) — the latter would shadow the
    auto_seed() function in this module (TypeError: 'bool' object is not
    callable).
    """
    conn = db.init_db(settings.db_path)
    if auto_seed_kb:
        auto_seed(conn)
    client = LLMClient(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        models=[settings.primary_model, settings.fallback_model],
    )
    app = Application.builder().token(settings.telegram_bot_token).build()
    app.bot_data["settings"] = settings
    app.bot_data["conn"] = conn
    app.bot_data["llm_client"] = client

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("today", cmd_today))
    app.add_handler(CommandHandler("summary", cmd_summary))
    app.add_handler(CommandHandler("log", cmd_log))
    app.add_handler(CommandHandler("weight", cmd_weight))
    app.add_handler(CommandHandler("phase", cmd_phase))
    app.add_handler(CommandHandler("personas", cmd_personas))
    app.add_handler(CommandHandler("notify", cmd_notify))
    app.add_handler(CommandHandler("mute", cmd_mute))
    app.add_handler(CommandHandler("target", cmd_target))
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(handle_callback))
    scheduler.register_jobs(app)
    app.post_init = _set_commands
    return app


def main() -> None:
    from logging_config import setup_logging

    setup_logging()
    settings = config.load_settings()
    app = build_application(settings)
    log.info("Starting polling…")
    app.run_polling()


if __name__ == "__main__":
    main()
