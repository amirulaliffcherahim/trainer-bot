# ATrainersBot — Telegram AI Trainer Bot

A personal AI trainer that lives in Telegram. Four expert personas — **runner
coach, calisthenics coach, mobility coach, physio** — think about every message
in parallel and merge into one coherent answer, with safety rules that can
never be overridden.

**Fully event-agnostic:** the bot learns your event, goal, target pace, and
training calendar from what YOU tell it (profile + `/target` + seeded phase
calendar) — nothing is baked in. No personal data, no hardcoded plans.

> **Status:** all 9 phases landed. 173+ tests, hermetic (no network needed).

## Why this design

Most AI trainers are a single model answering from memory. That produces
confident, wrong advice. This bot is engineered around one law:

> **The AI does the talking. The code does the math.**

- **Deterministic computation** — pace, volume trends, fatigue, rollups are
  computed in code from validated database rows. The LLM never does arithmetic.
- **Committee synthesis** — 4 focused experts draft in parallel
  (`asyncio.gather`), an editor merges them. Conflicts are surfaced, never
  hidden; the physio's advice always wins.
- **Grounded knowledge** — a curated, per-persona knowledge base (pacing,
  calisthenics progressions, mobility routines, physio triage + rehab) is
  retrieved and cited (`[SOURCE: ...]`). No match → the bot says "no data",
  never invents.
- **Verified screenshots** — Strava screenshots are OCR'd, the pace is
  recomputed in code, and every number is echoed back for confirmation before
  it enters your history.
- **Evolution, not drift** — training phases, weekly rollups, and milestone
  re-plan gates keep advice accurate over months, not just day one.
- **Proactive, not naggy** — run reminders, Sunday recaps, and coach
  suggestions (max 2/day, quiet at night, `/mute` respected, per-type
  toggles via `/notify`).

## Architecture

```
Telegram ──> bot.py (handlers, allowlist gate, debounce)
                 │
                 ├──> scheduler.py   (run reminders, Sunday recap, suggestions)
                 ├──> guardrails.py  (red-flag rules run FIRST, in code)
                 ├──> extract.py     (LLM: text → validated structured JSON)
                 ├──> facts.py       (code: rollups, trends, pace math)
                 ├──> retrieval.py   (per-persona KB, local embeddings, cosine)
                 ├──> personas/      (4 expert role prompts, config files)
                 ├──> synthesize.py  (4 parallel drafts → 1 merged answer)
                 ├──> validate.py    (citations present, numbers match facts)
                 ├──> suggest.py     (10 deterministic triggers, anti-nag caps)
                 ├──> predict.py     (Riegel race-time prediction, ±5% band)
                 └──> db.py          (SQLite, forward-only migrations)
```

Models: **DeepSeek V4-Flash** (primary, OpenAI-compatible API) with fallback
chain → `deepseek-v4-pro` → deterministic degraded mode. Screenshots use local
OCR (free); knowledge embeddings are local (`sentence-transformers`). No cloud
vision required.

## Quick start

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   |   Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env    # fill in your keys
python -m pytest tests/ -v
```

Required environment variables (see `.env.example`):

| Variable | Where to get it |
|---|---|
| `TELEGRAM_BOT_TOKEN` | [@BotFather](https://t.me/BotFather) — `/newbot` |
| `DEEPSEEK_API_KEY` | [platform.deepseek.com](https://platform.deepseek.com) |
| `ALLOWED_USER_IDS` | your Telegram user ID — [@userinfobot](https://t.me/userinfobot) |

Optional: `VISION_API_KEY` (Gemini Flash) — only if you upgrade the screenshot
reader from local OCR to a vision LLM.

## Making it yours (dynamic setup)

1. `/start` → set your profile (weight, etc.)
2. Tell the bot your event in plain chat — it stores what it learns in your
   profile and answers relative to it.
3. Seed the phase calendar + workout plan (Phase 0 seed script) for your own
   event dates, or let the bot work phase-less with what you share.
4. `/notify` → toggle run reminders, Sunday recap, and coach suggestions.

## Notifications

| Type | When | Toggle |
|---|---|---|
| Run reminder | Daily at `RUN_REMIND_TIME` if a session is scheduled | `/notify` |
| Sunday recap | Sundays 09:00 — volume, RPE, fatigue, streak, month total | `/notify` |
| Coach suggestions | Hourly 08:00–21:00, max 2/day | `/notify` + `/mute` |

Every push is sent at most once per day (dedup table); dismissals silence a
suggestion type for 7 days.

## Security (read this)

- **Allowlist gate:** only `ALLOWED_USER_IDS` may use the bot. Everyone else is
  silently rejected before any processing — no LLM, no OCR, no DB access.
- **Secrets:** `.env` is gitignored. If a token is ever shared anywhere, revoke
  it immediately (BotFather → `/revoke`) and generate a new one.
- **Data:** the SQLite database holds personal health data and never enters
  this repo. Real screenshots are user-provided and gitignored; the public
  test suite uses synthetic data only.
- **No webhook:** the bot uses long-polling — there is no public endpoint to
  attack.
- **Logging:** secrets and Bearer tokens are redacted before writing.
- Enable **GitHub secret scanning + push protection** and **Dependabot** on
  your fork.

## Project structure

```
config.py          env loading, fail-fast validation
bot.py             Telegram wiring (handlers, allowlist gate, jobs)
scheduler.py       run reminders, Sunday recap, suggestion pushes
db.py              SQLite + forward-only migration runner
migrations/        schema migrations (001 init … 004 notifications)
extract.py         text → validated structured data (one corrective re-prompt)
facts.py           deterministic computed facts block for prompts
personas/          the 4 expert role prompts (config, not code)
knowledge/         per-persona knowledge corpora (RAG source)
retrieval.py       embeddings + cosine top-k with threshold
ingest_kb.py       corpus → kb_chunks (CLI: python ingest_kb.py --help)
guardrails.py      red-flag rules, volume caps, symptom signals
synthesize.py      concurrent persona passes + editor merge
validate.py        output validation (citations, numbers)
suggest.py         10 deterministic suggestion triggers + anti-nag caps
predict.py         Riegel race-time prediction
replan.py          milestone re-plan proposals (never auto-applied)
retention.py       streaks, monthly totals, Sunday recap
challenges.py      weekly challenge templates + tracking
backup.py          atomic SQLite backups (30-day retention)
ocr.py             local OCR (4096px cap, optional vision upgrade)
strava.py          screenshot pipeline: math check → echo-confirm → verified
workouts.py        phase-aware /today queries
eval/              golden cases + synthetic images + regression gate
tests/             pytest suite (hermetic, no network)
```

## Deployment

### PM2 (no Docker)

```bash
pip install pm2  # or npm i -g pm2
pm2 start ecosystem.config.js
pm2 save && pm2 startup
pm2 logs trainer-bot
# daily backup (cron):
# 0 3 * * * cd /path/to/trainer-bot && .venv/bin/python backup.py trainer_data.db backups/ >> logs/backup.log 2>&1
```

### Docker

```bash
cp .env.example .env
docker compose up -d --build
docker compose run --rm backup   # manual backup
```

- Runs as a **non-root** user; SQLite persists in a named volume, logs in
  `./logs`. Long-polling — no exposed port.
- Backups: atomic online snapshot (`trainer_data_YYYY-MM-DD.db`), 30-day
  retention. Restore (bot stopped):
  `python -c "from backup import restore_db; restore_db('backups/trainer_data_2026-01-01.db', 'trainer_data.db')"`

## Roadmap

- [x] Phase 1 — Foundation (scaffold, env, migrations, DB, LLM client, logging)
- [x] Phase 2 — Extraction & facts (structured logs, rollups, pace math)
- [x] Phase 3 — Persona layer (4 role prompts, KB corpora, retrieval, guardrails)
- [x] Phase 4 — Synthesis (concurrent drafts → merged answer) & validation
- [x] Phase 5 — Telegram handlers + Strava screenshot pipeline
- [x] Phase 6 — Suggestion engine + race-time prediction
- [x] Phase 7 — Eval suite (regression gate)
- [x] Phase 8 — Re-plan gates + retention
- [x] Phase 9 — Deployment (Docker, PM2, backups) + notifications

## License

MIT — see [LICENSE](LICENSE).
