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
import time
from datetime import date

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
        "🏃 I'm your trainer — four experts in one: runner coach, calisthenics "
        "coach, mobility coach, physio.\n\n"
        "Log runs with text (\"easy 5km, RPE 6\") or Strava screenshots, ask "
        "anything, and I'll answer with all four perspectives.\n\n"
        "Commands: /today /summary /log /weight /phase /personas"
    )
    if phase:
        intro += f"\n\n📅 Current phase: {phase['phase_name']}"
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
    conn.commit()
    await update.message.reply_text(f"Weight updated: {weight} kg ✅")


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

    # 2. Structured extraction (one corrective re-prompt inside).
    try:
        extracted = await extract.extract_log(client, text)
    except extract.ExtractionFailed:
        await update.message.reply_text(
            "I couldn't parse that. Try: \"easy 5km, RPE 6, legs tired\"."
        )
        return
    except AllModelsFailed:
        await update.message.reply_text(
            "⚠️ AI unavailable right now. Try again in a minute."
        )
        return

    # 3. Computed facts from real data (code, not AI).
    rows = db.get_recent_history(conn, user_id)
    fb = facts.compute_facts(rows, today=date.today())

    # 4–5. Retrieval + 4 concurrent persona passes + editor merge.
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
        )
    except AllModelsFailed:
        await update.message.reply_text(
            "⚠️ AI unavailable right now. Degraded mode: check /today and /summary."
        )
        return

    await update.message.reply_text(answer)

    # 6. Store the log (structured values from extraction; never AI-derived pace).
    db.save_log(
        conn,
        date=date.today().isoformat(),
        user_id=user_id,
        user_input=text,
        ai_response=answer,
        rpe=extracted.rpe,
        fatigue_level=extracted.fatigue_level,
        weight_kg=extracted.weight_kg,
        sleep_hours=extracted.sleep_hours,
        session_type=extracted.session_type,
        distance_km=extracted.distance_km,
        moving_time_min=extracted.moving_time_min,
        completed=1 if extracted.completed else 0,
        model_used=client.last_model_used,
        prompt_version="pipeline-v1",
    )


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

    await update.message.reply_text("🔍 Reading your screenshot…")

    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        image_bytes = bytes(await file.download_as_bytearray())
    except Exception as exc:  # noqa: BLE001 — Telegram errors surface as plain failure
        log.warning("photo download failed: %s", exc)
        await update.message.reply_text("Couldn't download that image.")
        return

    ocr_text = await asyncio.to_thread(
        ocr.extract_text, image_bytes, vision_api_key=settings.vision_api_key
    )
    if not ocr_text.strip():
        await update.message.reply_text(
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
        await update.message.reply_text(
            "Couldn't read the numbers. Please type distance and time manually, "
            "e.g. \"10.42 km, 72:38\"."
        )
        return
    except AllModelsFailed:
        await update.message.reply_text("⚠️ AI unavailable — try again in a minute.")
        return

    draft_id = DRAFTS.put(read)
    await update.message.reply_text(
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


def build_application(settings: Settings, *, auto_seed: bool = True) -> Application:
    conn = db.init_db(settings.db_path)
    if auto_seed:
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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(handle_callback))
    scheduler.register_jobs(app)
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
