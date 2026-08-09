# Stuff Needed — Checklist

Everything required to build and run the iteration-2 trainer bot, by category. Tick as you collect each item.

## 1. Accounts & Keys

- [x] **Telegram bot token** — create via [@BotFather](https://t.me/BotFather): `/newbot` → copy token
- [ ] **DeepSeek API key** — https://platform.deepseek.com (primary model: `deepseek-v4-flash`, text + JSON + thinking mode, OpenAI-compatible)
- [ ] **Vision API key — OPTIONAL.** Default screenshot route is fully local: OCR (EasyOCR/PaddleOCR) → DeepSeek parses text. No extra key needed. Only if local OCR accuracy disappoints: Google AI Studio key for Gemini Flash (https://aistudio.google.com/apikey) as accuracy-upgrade route
- [x] **Your Telegram user ID** — get via [@userinfobot](https://t.me/userinfobot) → `ALLOWED_USER_IDS=<your_id>` in `.env` (single-user bot)
- [ ] **Race registrations confirmed** — SELMAR Half Marathon (Nov 1, 2026), TwinCity (Jan 24, 2027) — dates drive the whole phase calendar

## 2. Software (local dev)

- [ ] Python 3.11+
- [ ] Git
- [ ] VS Code / editor of choice
- [ ] Optional: Docker (only for deployment step)

## 3. Python Dependencies (requirements.txt)

| Package | Why |
|---|---|
| `python-telegram-bot>=20.0` | Telegram API (async) |
| `openai` | DeepSeek client (OpenAI-compatible, base_url `https://api.deepseek.com`) |
| `easyocr` (or `paddleocr`) | Local OCR for screenshots — free, no cloud (heavier dep: torch) |
| `markitdown` | Free local converter for KB ingestion: PDFs/Word/HTML → Markdown → chunks |
| `google-genai` | OPTIONAL — only if local OCR accuracy disappoints (Gemini Flash route) |
| `sentence-transformers` | Local embeddings for KB (free, CPU) |
| `pillow` | Image handling |
| `pydantic` | Validates AI-extracted JSON (accuracy-critical) |
| `python-dotenv` | `.env` config |
| `pytest` | Eval harness (dev-only) |

## 4. Persona Definitions (the 4 experts)

Write one `personas/<name>.md` per expert. Each needs: role prompt, scope/rules, relevance signals, guardrails.

- [ ] **Runner persona** — HM training, pacing (7:06–7:10/km), phases, volume rules, heat running
- [ ] **Calisthenics persona** — bodyweight progressions, 3x/week split, overload rules, strength↔running integration
- [ ] **Mobility persona** — pre-run activation, warm-up/cool-down, quad/hip/ankle routines
- [ ] **Physio persona** — triage, red flags, rehab progressions (quad tendonitis, shin splints), load management
- [ ] Conflict hierarchy documented (physio > runner > calisthenics > mobility)

## 5. Knowledge Base Source Material (per persona)

~50–100 chunks total, split into 4 corpora under `knowledge/`:

### `runner/`
- [ ] Sub-3 HM pacing strategy + negative split notes
- [ ] HM training principles, weekly volume progression (≤10%/week rule)
- [ ] Tropical weather (KL/Selangor) hydration + heat adaptation

### `calisthenics/`
- [ ] Bodyweight progressions: push, pull, squat, core (levels + when to advance)
- [ ] 3x/week strength split aligned with run schedule
- [ ] Strength↔running integration rules (which days, intensity)

### `mobility/`
- [ ] Pre-run activation routine
- [ ] Warm-up / cool-down protocols
- [ ] Quad, hip, ankle mobility + tightness routines

### `physio/`
- [ ] Injury triage + red flags (when to stop, when to see a professional)
- [ ] Quadriceps tendonitis rehab progression
- [ ] Shin splints rehab progression
- [ ] Load management around injury (what's safe to keep doing)

## 6. Strava Accuracy Kit (the priority)

- [ ] **10–20 real Strava screenshots from your own account** with known values (distance, time, pace) — this becomes the ground-truth test set
- [ ] A few deliberately inconsistent examples for testing (wrong pace display, cropped screenshot) — to prove the math check catches errors
- [ ] Optional (future): Strava share-link / GPX export access for zero-OCR accuracy

## 7. Data to Have Ready

- [ ] Athlete profile: height 175 cm, weight 55 kg, target race, target pace 7:10/km
- [ ] Weekly schedule: 3x run (Tue easy/tempo, Thu easy, Sat long) + 3x strength (Mon upper, Thu legs, Fri core) + 2 rest (Wed, Sun)
- [ ] Training-phase calendar (computed from race dates — Phase 0 of the plan)
- [ ] Eval cases: 8–10 golden Q&A per persona (32–40) + ~10 cross-persona conflict cases

## 8. Hardware & Hosting

- [ ] Phone (for testing)
- [ ] Dev machine (your current one is fine)
- [ ] Production host: cheap VPS (~1 GB RAM is plenty) **or** an always-on machine at home
- [ ] (No domain / TLS needed — the bot uses long-polling, no webhook)

## 9. Time Budget (rough)

| Phase | Effort |
|---|---|
| 0–1 Foundation | ~2–3 sessions |
| 2–4 AI engine + personas + synthesis | ~4–6 sessions |
| 5 Strava pipeline + Telegram | ~3–4 sessions |
| 6 Eval suite | ~2–3 sessions |
| 7–8 Re-plan + deploy | ~2 sessions |

Total: ~3–4 weeks of part-time work. Persona content writing (KB) is the biggest chunk — start early.

## 10. Running Costs (per month)

- [ ] DeepSeek V4-Flash: cheap (pricing page didn't render at research time — historically ~$0.2–0.3/M input, ~$1/M output for DeepSeek chat models; V4-Flash is the budget tier — verify at build). 6 calls/message at ~50–100 messages/day = pennies/month
- [ ] Vision: $0 by default (local OCR). If upgraded to Gemini Flash: ~1–2 calls/day = pennies/month
- [ ] Embeddings: local, free
- [ ] VPS (if used): $5–10
- [ ] Everything else: free

## 11. Operational To-Dos (after launch)

- [ ] Daily backup of `trainer_data.db` (sqlite3 .backup, 30-day retention)
- [ ] Sunday recap push runs unattended
- [ ] Monthly: review eval results, re-ingest KB if edited, run replan gate
- [ ] Watch for Gemini model deprecation notices (abstraction layer makes swap = one config change)
- [ ] Review persona drafts in `daily_logs.persona_drafts` monthly — catch drifting persona quality early

## 12. Security Checklist (public repo)

- [ ] **Revoke bot token** — BotFather `/revoke` → new token into `.env` only (old one was shared in chat)
- [ ] `.gitignore` created FIRST: `.env`, `*.db`, `uploads/`, `__pycache__/`, `eval/real/`
- [ ] `.env.example` committed, documented; real `.env` never
- [ ] Pinned deps (`==`) in requirements.txt
- [ ] GitHub: **secret scanning + push protection** ON (free for public repos)
- [ ] GitHub: **Dependabot** ON
- [ ] Synthetic Strava test images for the public eval suite (real screenshots stay out of repo, in `eval/real/`)
- [ ] Allowlist gate is first thing in every handler (silent reject for strangers)
- [ ] Debounce (1 msg/sec) + image size cap (4096px) implemented
- [ ] No secrets in logs or error messages
