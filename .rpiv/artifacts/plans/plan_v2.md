# PLAN — Telegram AI Trainer Bot (Iteration 2)

**Source design doc:** `planning/plan_v2.md` (full detail — architecture, personas, schema, security). This artifact is the executable phase checklist; the source doc is the reference.

**Status:** Implementation in progress — Phase 1 (foundation) owned by current run.

**Goal:** A trainer bot whose advice stays accurate over months of use. 4 merged personas (runner / calisthenics / mobility / physio), committee synthesis, Strava-screenshot accuracy pipeline, proactive suggestion engine, eval-gated changes. Design laws: accuracy over speed; AI talks, code does math; computed facts > retrieved chunks > model memory; allowlist is the security gate.

**Security constraints (public GitHub repo):** `.gitignore` FIRST (`.env`, `*.db`, `uploads/`, `__pycache__/`, `eval/real/`); `.env.example` committed, real `.env` never; pinned deps (`==`); real Strava screenshots and SQLite health data never in repo (synthetic test images only); allowlist gate first in every handler; debounce 1 msg/sec; image cap 4096px; no secrets in logs. See source doc §10 Security.

---

## Phase 0: Calendar & Scope

Pin the training calendar — everything downstream reads it.

**files:**
- `planning/plan_v2.md` (calendar section)
- `config/seed_data.py` (Phase 1 foundation provides the seed container; Phase 0 fills training_phases seed) — *note: folded into Phase 1/2 as seed data; Phase 0 is a confirmation gate, not code*

**tasks:**
- [ ] User confirms race dates: SELMAR Half Marathon Nov 1 2026, TwinCity Jan 24 2027 (+ registration) and that today is BEFORE Jul 27 2026 (program start)
- [ ] Seed `training_phases` + `workout_plan` from `knowledge/runner/selmar_program.md` (14-week SELMAR block Jul 27 2026 + 12-week TwinCity extension) — targets: SELMAR 2:30:00 primary / 2:45:00 backup (7:06–7:49/km), TwinCity sub-2:30/2:25 (6:50–7:00/km)
- [ ] Define per-phase rules: volume range, pace targets, long-run distance, strength focus, rest-day rules

#### Automated Verification:
- [ ] Phase table in seed data has contiguous date ranges covering both race dates

---

## Phase 1: Foundation (scaffold, env, deps, migrations, db, llm client, logging)

**files:**
- `.gitignore` (FIRST — security)
- `requirements.txt`, `requirements-dev.txt` (pinned `==`)
- `.env.example` (documented vars; real `.env` never committed)
- `config.py` (env loading, fail-fast validation, secret redaction list)
- `db.py` (connection, `schema_migrations` runner, `init_db()`)
- `migrations/001_init.sql` (full v2 schema — all tables from source doc §3.2)
- `logging_config.py` (rotation, redaction filter)
- `llm_client.py` (DeepSeek OpenAI-compatible client: retry/backoff, fallback chain flash→pro→degraded, JSON mode, model-used logging)
- `tests/test_config.py`, `tests/test_db.py`, `tests/test_llm_client.py`
- `README.md` (setup, security note, .env.example pointer)

**tasks:**
- [x] `.gitignore`: `.env`, `*.db`, `*.db-journal`, `uploads/`, `__pycache__/`, `.venv/`, `venv/`, `eval/real/`, `logs/`, `.pytest_cache/`, `.coverage`
- [x] `requirements.txt` pinned: openai==2.53.0, pydantic==2.13.4, python-dotenv==1.2.2, python-telegram-bot==22.8, pillow==12.3.0 (heavy deps — easyocr/markitdown/sentence-transformers — land in their phases)
- [x] `requirements-dev.txt`: pytest==9.1.1, pytest-asyncio==1.4.0
- [x] `.env.example`: TELEGRAM_BOT_TOKEN, DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, VISION_API_KEY (optional), ALLOWED_USER_IDS, PRIMARY_MODEL, FALLBACK_MODEL, LOG_LEVEL, DB_PATH — each documented
- [x] `config.py`: pydantic Settings, loads `.env`, fail-fast with clear message listing missing vars, `SECRET_ENV_NAMES` for redaction
- [x] `db.py`: `get_conn(db_path)` (row_factory), migration runner (schema_migrations table, applies `migrations/*.sql` in order, transactional), `init_db(db_path)` idempotent
- [x] `migrations/001_init.sql`: daily_logs, athlete_profile, training_phases, workout_plan, weekly_rollups, kb_chunks, eval_cases, suggestions_log, challenges, target_history, performance_anchors (schema per source doc §3.2)
- [x] `logging_config.py`: `setup_logging(level, log_dir)` — RotatingFileHandler + console, RedactingFilter masking secret values
- [x] `llm_client.py`: `LLMClient` (injectable OpenAI client for tests), `chat()` with exponential backoff + jitter on 429/5xx/timeout, fallback chain PRIMARY_MODEL → FALLBACK_MODEL → raise `AllModelsFailed` (caller chooses degraded mode), `chat_json()` with `response_format={"type": "json_object"}`, `last_model_used`
- [x] `tests/`: config missing-var fails; db init creates all tables + idempotent + migration recorded; llm_client fallback fires on primary failure (mocked), retry backoff bounded
- [x] `README.md`: setup steps, security note (allowlist, .env handling, no real data in repo)

#### Automated Verification:
- [x] `python -m pytest tests/ -v` — all Phase 1 tests pass
- [x] `python -c "from db import init_db; c = init_db(':memory:')"` — no error, tables exist
- [x] `python -c "import config"` without env → fails fast with missing-var message
- [x] llm_client fallback test: primary model raises → fallback model used (mocked, no network)

---

## Phase 2: Extraction & Facts

**files:**
- `extract.py` (LLM pass #1: text → structured JSON, Pydantic-validated, one corrective re-prompt, range checks)
- `facts.py` (7-day RPE mean, fatigue trend, volume delta, weekly % increase, pace trends)
- `db.py` additions: `save_log()`, `get_recent_history()`, `compute_weekly_rollup()`
- `tests/test_extract.py`, `tests/test_facts.py`

**tasks:**
- [x] Pydantic schemas: `LogExtraction` (rpe 1–10, fatigue 1–10, weight 30–200, session_type, notes)
- [x] Malaysian context (Phase 1 review): recognize colloquial terms (betis/quad niggle, sub-7 pace, panas terik, hujan lebat); factor KL/Selangor heat/humidity into hydration + pace drift
- [x] Extraction retry: validation failure → one corrective re-prompt → second failure surfaces to user
- [x] `facts.py` computes from DB, pure functions, injected into prompt as facts block
- [x] Rollups: weekly volume_km, avg_rpe, avg_fatigue, weight_trend, completed_sessions, long_run_km

#### Automated Verification:
- [x] Malformed input → clean JSON or corrective re-prompt (unit tests)
- [x] Out-of-range values rejected (rpe=15 → rejected)
- [x] Rollup numbers correct on synthetic week of logs

#### Reconciliation
- `tests/test_db.py`: replace `{"001_init.sql", "002_indexes.sql"}` → `{"001_init.sql", "002_indexes.sql", "003_log_run_metrics.sql"}` — Phase 2 added migration 003 (distance/pace columns required by volume rollups); the exact-set assertion must include it (note: Python target, outside reconcile's auto-applied extensions — route to owning phase if rejected)

---

## Phase 3: Persona Layer

**files:**
- `personas/runner.md`, `personas/calisthenics.md`, `personas/mobility.md`, `personas/physio.md` (role prompt + scope + rules + relevance signals)
- `knowledge/runner/`, `knowledge/calisthenics/`, `knowledge/mobility/`, `knowledge/physio/` (curated corpora)
- `ingest_kb.py` (MarkItDown → chunk by heading → local embeddings → kb_chunks)
- `retrieval.py` (per-persona top-k=4, threshold ≥0.7, cosine in Python)
- `guardrails.py` (red-flag rules in code, physio highest veto, hard caps: ≤10% volume, symptom list)
- `tests/test_retrieval.py`, `tests/test_guardrails.py`

**tasks:**
- [x] 4 persona role prompts written + versioned
- [x] KB corpora drafted (source doc §4.4 list) + ingested
- [x] Retrieval per persona with threshold + explicit "no match"
- [x] Guardrails: red flags bypass AI entirely; caps enforced in code

#### Automated Verification:
- [x] Retrieval: correct chunk surfaces for "shin pain after long run" (physio corpus)
- [x] Guardrails: "chest pain during run" → canned response, AI bypassed
- [x] Below-threshold query → "no knowledge-base match" for that persona

---

## Phase 4: Synthesis

**files:**
- `synthesize.py` (merge 4 drafts, conflict hierarchy, output validation)
- `validate.py` (citation presence, no number contradicts facts block)
- `tests/test_synthesize.py`, `tests/test_validate.py`

**tasks:**
- [ ] Synthesis pass receives 4 drafts + facts + hierarchy; conflicts surfaced explicitly
- [ ] Output validation in code: citations present OR "no data"; numbers match facts block
- [ ] Hierarchy: physio > runner > calisthenics > mobility

#### Automated Verification:
- [ ] Conflict case: quad flare + long run scheduled → physio wins, conflict surfaced (unit test)
- [ ] No-citation output rejected

---

## Phase 5: Telegram Layer + Strava Pipeline

**files:**
- `bot.py` (handlers, allowlist gate FIRST, debounce, callback router)
- `strava.py` (screenshot pipeline: read pass → math check → plausibility → plan comparison → echo-confirm → store verified)
- `ocr.py` (local OCR wrapper: EasyOCR/PaddleOCR → text; 4096px cap; Tesseract fallback)
- `workouts.py` (`/today` = training_phases × workout_plan)
- `tests/test_strava.py`, `tests/test_auth.py`

**tasks:**
- [ ] Allowlist gate first in every handler; silent reject for strangers
- [ ] Debounce 1 msg/sec; image cap 4096px
- [ ] Strava pipeline per source doc §5: pace computed in code, UNCERTAIN flag, echo-confirm buttons, verified=1 storage
- [ ] Commands: /start /today /summary /log /weight /phase /personas (buttons)
- [ ] Inline buttons: InlineKeyboardMarkup + CallbackQueryHandler
- [ ] Telegram `callback_data` 64-byte hard limit (Phase 1 review): buttons use short state refs (e.g. `cf:<draft_id>`), pending drafts in memory TTL dict or SQLite — never embed run stats in callback payloads

#### Automated Verification:
- [ ] Auth test: unknown user → silent reject, no processing
- [ ] Math check test: doctored screenshot (pace ≠ time/distance) → UNCERTAIN flagged
- [ ] Strava ground-truth set (synthetic images in repo): extracted fields match known values

---

## Phase 6: Suggestion Engine + Prediction

**files:**
- `suggest.py` (deterministic triggers, anti-nag caps, dismissal dedup, quiet hours)
- `challenges.py` (templates per phase × persona, accept/skip/completed tracking)
- `predict.py` (Riegel formula, performance_anchors, ±5% band, exponent refit with 2+ anchors)
- `tests/test_suggest.py`, `tests/test_predict.py`

**tasks:**
- [ ] Trigger catalog (source doc §7.2): all 10 triggers in code
- [ ] Anti-nag caps: 2 pushes/day, quiet hours, taper silence, dismiss → 7-day dedup, /mute
- [ ] Prediction: Riegel math, anchor selection (best verified effort), range output, never auto-changes target

#### Automated Verification:
- [ ] Trigger tests: correct triggers fire, none spuriously
- [ ] Anti-nag tests: caps enforced
- [ ] Prediction: Riegel math exact; ±5% band; refit correct with 2 anchors

---

## Phase 7: Eval Suite (gate)

**files:**
- `eval/cases.yaml` (golden cases: 8–10 per persona + ~10 conflicts)
- `eval/runner.py` (assertion checks: expected facts, advice direction, citations)
- `eval/synthetic_images.py` (generates synthetic Strava-like test images — public-safe)
- `tests/test_eval_gate.py`

**tasks:**
- [ ] Golden cases per persona + conflicts (physio wins)
- [ ] Regression gate: prompt/KB/model/persona change must pass full suite
- [ ] Synthetic image generator (no real screenshots in repo)

#### Automated Verification:
- [ ] Deliberately bad prompt change fails the gate (test)
- [ ] Full eval suite green

---

## Phase 8: Re-plan Gates + Retention

**files:**
- `replan.py` (4–6 week gate: pace trend vs target, volume rule, weight, physio flags, prediction gap)
- `retention.py` (Sunday recap push, milestones, streaks, silence check)
- `tests/test_replan.py`, `tests/test_retention.py`

**tasks:**
- [ ] Replan proposal format: data-driven, user confirms, never auto-applies
- [ ] Sunday recap + milestone celebrations + streak tracking

#### Automated Verification:
- [ ] Replan proposes correct target from synthetic 6-week history
- [ ] Recap content correct from rollups

---

## Phase 9: Deployment

**files:**
- `Dockerfile` (python:3.11-slim, non-root)
- `docker-compose.yml` (bot + sqlite volume + backups)
- `backup.py` (daily sqlite3 .backup, 30-day retention)
- `README.md` deployment section

**tasks:**
- [ ] Containerized, non-root, no secrets in image
- [ ] Backup restores verified

#### Automated Verification:
- [ ] `docker build` succeeds; container starts with valid env
- [ ] Backup → restore round-trip test

---

## Whole-plan Success Criteria (validate stage)

Source doc §12 items 1–15 (4-perspective answers, conflict handling, Strava accuracy, suggestion discipline, prediction honesty, migration test, eval gate, degraded mode, persona pluggability).
