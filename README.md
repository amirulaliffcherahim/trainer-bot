# ATrainersBot — Telegram AI Trainer Bot

A personal AI trainer that lives in Telegram. Four expert personas — **runner
coach, calisthenics coach, mobility coach, physio** — think about every message
in parallel and merge into one coherent answer, with safety rules that can
never be overridden.

Built for a real training goal: the SELMAR Half Marathon (Nov 1 2026, target
**2:30:00**) and TwinCity Half Marathon (Jan 24 2027), in Kuala Lumpur heat.

> **Status:** early development (Phases 1–3 landed: foundation, extraction &
> facts, persona layer). Not yet runnable as a live bot.

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

## Architecture

```
Telegram ──> bot.py (handlers, allowlist gate)
                 │
                 ├──> guardrails.py   (red-flag rules run FIRST, in code)
                 ├──> extract.py      (LLM: text → validated structured JSON)
                 ├──> facts.py        (code: rollups, trends, pace math)
                 ├──> retrieval.py    (per-persona KB, local embeddings, cosine)
                 ├──> personas/       (4 expert role prompts, config files)
                 ├──> synthesize.py   (4 parallel drafts → 1 merged answer)
                 ├──> validate.py     (citations present, numbers match facts)
                 └──> db.py           (SQLite, forward-only migrations)
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
- If you deploy this, enable **GitHub secret scanning + push protection** and
  **Dependabot** on your fork.

## Project structure

```
config.py          env loading, fail-fast validation
db.py              SQLite + forward-only migration runner
migrations/        schema migrations (001 init, 002 indexes, 003 run metrics)
extract.py         text → validated structured data (one corrective re-prompt)
facts.py           deterministic computed facts block for prompts
personas/          the 4 expert role prompts (config, not code)
knowledge/         per-persona knowledge corpora (RAG source)
retrieval.py       embeddings + cosine top-k with threshold
ingest_kb.py       corpus → kb_chunks (CLI: python ingest_kb.py --help)
guardrails.py      red-flag rules, volume caps, symptom signals
synthesize.py      concurrent persona passes + editor merge
validate.py        output validation (citations, numbers)
llm_client.py      DeepSeek client: retry/backoff, fallback chain, JSON mode
logging_config.py  rotation + secret redaction
tests/             pytest suite (60 tests)
planning/          design docs, user flows, decision records
```

## Knowledge base

The bot's advice is grounded in `knowledge/` — split by persona:

- `runner/` — SELMAR 2:30:00 pacing strategy, the 14-week program, volume
  progression, KL heat/humidity, rest-day rules
- `calisthenics/` — the athlete's fixed exercise list, progressions, split
- `mobility/` — pre-run activation, cool-down, daily 10-minute routine
- `physio/` — triage + red flags, DOMS vs injury, quad tendonitis and shin
  splint rehab, Yoko Yoko safe use

## Roadmap

- [x] Phase 1 — Foundation (scaffold, env, migrations, DB, LLM client, logging)
- [x] Phase 2 — Extraction & facts (structured logs, rollups, pace math)
- [x] Phase 3 — Persona layer (4 role prompts, KB corpora, retrieval, guardrails)
- [ ] Phase 4 — Synthesis (concurrent drafts → merged answer) & validation
- [ ] Phase 5 — Telegram handlers + Strava screenshot pipeline
- [ ] Phase 6 — Suggestion engine + race-time prediction
- [ ] Phase 7 — Eval suite (regression gate)
- [ ] Phase 8 — Re-plan gates + retention
- [ ] Phase 9 — Deployment (Docker/systemd, backups)

## License

MIT — see [LICENSE](LICENSE).
