Here is a complete, production-ready **`PLAN.md`** file engineered specifically for building your **Telegram AI Trainer Bot**.

You can drop this markdown file straight into your project directory and use your AI coding agents / CLI tools (e.g., OpenCode, ZeroClaw, Antigravity) to read and execute the plan step-by-step.

---

# `PLAN.md` — Telegram AI Personal Trainer Bot Blueprint

## 📌 Executive Summary

Build a robust, asynchronous **Telegram AI Personal Trainer Bot** using Python, `python-telegram-bot`, `google-genai`, and `SQLite`. The bot serves as an adaptive, multimodal coach for an athlete training for the **SELMAR Half Marathon** (Nov 1, 2026) and **TwinCity Half Marathon** (Jan 24, 2027).

---

## 🎯 Core Requirements & Specifications

### 1. Athlete Profile Context (Embedded System Prompt)

* **Demographics:** 175 cm, 55 kg (Underweight / Target: ~2,700 kcal daily / ~100g protein).
* **Primary Event:** SELMAR Half Marathon (Nov 1, 2026) -> Goal: Sub-3 Hours (Target Pace ~7:06 - 7:10 min/km).
* **Secondary Event:** TwinCity Half Marathon (Jan 24, 2027).
* **Schedule Split:** 3x Running (Tuesday Easy/Tempo, Thursday Easy, Saturday Long Run) + 3x Bodyweight Strength (Monday Upper, Thursday Legs, Friday Core) + 2 Rest Days (Wednesday, Sunday).
* **Safety Protocols:** Monitor for quadriceps tendonitis, shin splints, and hydration levels in tropical weather (Kuala Lumpur/Selangor).

### 2. Functional Capability Stack

* **Multimodal Vision:** Process screenshots (Strava, Garmin, Apple Health), meal photos (macro estimation), and posture/form photos using Gemini 1.5 Flash.
* **Persistent Memory:** Store daily training logs, mood/stress indicators, weather conditions, RPE, and body weight in SQLite.
* **Rolling Context Engine:** Feed the last 5 to 7 days of athlete history into the LLM prompt window on every interaction to provide personalized, fatigue-aware adaptations.
* **Command Suite:** `/start`, `/today`, `/summary`, `/log`, `/help`.

---

## 🏗️ Architecture & Database Schema

### Database Layout (`trainer_data.db`)

```sql
CREATE TABLE IF NOT EXISTS daily_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    date TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    user_input TEXT,
    has_image INTEGER DEFAULT 0,
    image_path TEXT,
    ai_response TEXT NOT NULL,
    rpe INTEGER,
    fatigue_level INTEGER,
    weight_kg REAL
);

CREATE TABLE IF NOT EXISTS athlete_profile (
    user_id INTEGER PRIMARY KEY,
    height_cm REAL DEFAULT 175.0,
    weight_kg REAL DEFAULT 55.0,
    target_race TEXT DEFAULT 'SELMAR Half Marathon 2026',
    target_pace TEXT DEFAULT '7:10 min/km'
);

```

---

## 📋 Implementation Roadmap & Tasks

### Phase 1: Environment & Core Setup

* [ ] Initialize Python virtual environment (`python -m venv venv`).
* [ ] Create `requirements.txt`:
```text
python-telegram-bot>=20.0
google-genai
pillow
pydantic
python-dotenv

```


* [ ] Setup `.env` file configuration:
```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
GEMINI_API_KEY=your_gemini_api_key
ALLOWED_USER_IDS=12345678,98765432

```



### Phase 2: Database & State Management Module (`db.py`)

* [ ] Implement `init_db()` to auto-create SQLite tables on startup.
* [ ] Implement `save_log(user_id, input_text, ai_response, has_image, image_path)`.
* [ ] Implement `get_recent_history(user_id, days=7)` returning structured markdown logs.
* [ ] Implement `get_weekly_summary_stats(user_id)` to calculate total completed sessions and average fatigue.

### Phase 3: AI / LLM Engine Module (`ai_engine.py`)

* [ ] Initialize Google GenAI client (`google.genai.Client`).
* [ ] Create system instruction template containing athlete context, current targets, and injury guardrails.
* [ ] Implement `generate_coach_advice(user_input, history_context, image_bytes=None)`.
* [ ] Add exception handling for API rate limits or network dropouts.

### Phase 4: Telegram Handler Integration (`bot.py`)

* [ ] Implement `/start` command with introductory quick-start guide.
* [ ] Implement `/today` command to fetch scheduled workouts based on current calendar date.
* [ ] Implement `/summary` command to display weekly completion stats.
* [ ] Implement message handler for `filters.TEXT` (text logs, daily stress, weather feel).
* [ ] Implement message handler for `filters.PHOTO` (download high-res photo, pass buffer to Gemini, store locally under `uploads/`).
* [ ] Implement security middleware to check `user_id` against `ALLOWED_USER_IDS` to prevent unauthorized usage.

### Phase 5: Production Hardening & Deployment

* [ ] Add robust error logging using `logging` module.
* [ ] Create `Dockerfile` for containerized deployment:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "bot.py"]

```


* [ ] Create `systemd` unit file or Docker Compose file for 24/7 background execution.

---

## 🧪 Verification & Acceptance Criteria

1. **Daily Log Verification:**
* **Input:** Send text: *"Work stress 8/10, hot weather 33C, tight right quad."*
* **Output:** Bot acknowledges history, adjusts today's load (recommends easy run or foam rolling), and records log in SQLite.


2. **Vision Processing Verification:**
* **Input:** Upload screenshot of Strava run with caption *"Saturday long run done."*
* **Output:** Bot reads distance/pace from image, compares against target pace (~7:10/km), provides recovery guidance, and saves photo reference.


3. **Memory Persistence Test:**
* **Input:** Ask *"How has my fatigue been looking over the past 3 days?"*
* **Output:** Bot summarizes recorded logs from SQLite accurately.
