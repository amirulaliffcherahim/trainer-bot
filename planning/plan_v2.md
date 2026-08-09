# PLAN v2 — Telegram AI Trainer Bot (Iteration 2)

**Status:** Planning (iteration 2)
**Supersedes:** `planning/first_plan.md`
**Goal:** A trainer bot whose advice stays **accurate over months of use** — not just on day one.

---

## 0. Design Laws (decided)

1. **Accuracy over speed.** The bot is deliberately not "instant." Multi-pass thinking, verification loops, and confirmation steps are features, not bugs. Fast-but-wrong is the failure mode we're designing against.
2. **The AI talks, the code does math.** All arithmetic, trends, validation, and rule enforcement happen in deterministic code. The AI never computes.
3. **Four personas, one trainer.** The bot always answers from 4 merged expert perspectives (below). Additional personas are pluggable later (nutrition, psychology) — the architecture treats a persona as a config, not a code change.
4. **Computed facts > retrieved chunks > model memory.** When sources conflict, the database-derived numbers win.
5. **The bot coaches, it doesn't just answer.** It proposes challenges, predicts race times, flags drift, and offers one-tap actions — but never nags, never pushes more than a capped number of times, and never acts without confirmation.

---

## 1. The 4-Persona Model

The bot is one trainer who thinks in four expert perspectives simultaneously:

| # | Persona | Domain | Veto power |
|---|---|---|---|
| 1 | **Distance Runner Trainer** | HM training, pacing, volume, phases, periodization, running form, tropical heat running | Load/volume caps |
| 2 | **Calisthenics Trainer** | Bodyweight strength (push, pull, squat, core), progressive overload, 3x/week split, strength↔running integration | Strength progression rules |
| 3 | **Mobility Trainer** | Flexibility, joint mobility, warm-up/cool-down, pre-run activation, addressing tightness (quads, hips, ankles) | Supplementary |
| 4 | **Physiotherapy Trainer** | Injury triage, red flags, rehab progressions (quad tendonitis, shin splints), load management around injury | **Highest — can veto anything** |

### 1.1 Persona anatomy (each persona is a config, not code)

```
personas/<persona>.md
├── role prompt        (expert identity, scope, style, rules — versioned)
├── knowledge/         (own KB section — retrieved separately)
├── guardrails         (own red-flag rules, evaluated in code)
└── relevance signals  (keywords that weight this persona in synthesis)
```

### 1.2 Committee synthesis (per message)

```
user message
   │
   ▼
1. guardrails.py        — ALL personas' red-flag rules run first (code).
   │                      Physio red flag → canned response, AI bypassed.
   ▼
2. extract.py           — LLM pass #1: message/image → structured JSON (Pydantic-validated)
   ▼
3. facts.py             — code: rollups, trends, pace math, plan comparison
   ▼
4. persona passes       — 4 LLM passes (parallel): each persona gets its own
   │                      role prompt + own KB retrieval (top-k=4) + shared facts
   │                      block. Each produces a draft + cited sources.
   ▼
5. synthesize.py        — LLM pass #6: merges 4 drafts into ONE coherent reply.
                          Conflict resolution by hierarchy (physio > runner >
                          calisthenics > mobility). Conflicts are surfaced,
                          not hidden: "physio rule: rest — skipping today's
                          run is the right call."
   ▼
6. validate.py          — citations present? no invented numbers? (code checks)
   ▼
7. db.py                — store log + persona drafts + model + prompt versions
   ▼
8. suggest.py           — trigger check: does this reply warrant a suggestion
                          + one-tap button? (see §7)
```

**Why 6 passes?** One model juggling 4 expert roles in a single prompt dilutes every role and lets conflicts hide. A panel of 4 focused experts + 1 editor produces measurably more accurate, safer answers. Cost: ~5–6 calls per message (persona passes run in parallel → ~3 sequential round-trips). Design law #1 makes this the right trade.

---

## 2. Fixed Calendar & Targets (Phase 0 — pin before anything else)

Race dates and targets drive everything. Work backward from them. (Reconciled
with the Gemini full-plan export — `planning/gemini_export.md` — which
contains the authoritative week-by-week program.)

### 2.1 Athlete profile & targets

- Demographics: 175 cm / 55 kg (underweight; surplus ~2,700 kcal/day,
  99–110 g protein/day, ~20–30 g every 3–4 h)
- Baselines: 5K 35:00, 10K 1:10:00 (~7:00/km)
- **SELMAR Half Marathon (Nov 1, 2026):** primary target **2:30:00**
  (2:29:47 @ 7:06/km); safe backup **2:45:00** (7:49/km). Race-day pacing:
  KM 1–3 @ ~7:20 → KM 4–16 @ ~7:05 → KM 17–21.1 @ ~7:00 (cumulative 2:29:47)
- **TwinCity Half Marathon (Jan 24, 2027):** target refinement sub-2:30 /
  2:25 (6:50–7:00/km)
- Location: Kuala Lumpur / Selangor — high heat & humidity (pace plans must
  carry a heat factor)

### 2.2 Training calendar (authoritative program from export)

**SELMAR 14-week block (starts Jul 27, 2026):** 3 runs/week (Tue/Thu/Sat),
volume 17 → 31 km, de-loads at W4/W8/W10, two 21.1 km trial runs (W8 @
8:00/km low-stress; W10 @ 7:10/km race-pace rehearsal), taper W11–13,
race W14. Full week-by-week table in `knowledge/runner/selmar_program.md`
(seed for `workout_plan`).

**TwinCity 12-week extension (Nov 2, 2026 → Jan 24, 2027):** active
recovery/reverse taper → base rebuild → build & threshold (tempo 6:40/km,
800s @ 6:30/km) → peak & simulation (21.1 km trial @ ~7:00/km on Jan 2) →
taper → race day.

**Before Jul 2026:** base phase (first-class) — easy miles, strength,
weight gain toward 55 kg+, heat adaptation, mobility. No race-specific
intensity.

### 2.3 Weekly skeleton (fixed)

- Mon: rest/dynamic + upper strength · Tue: easy/tempo/speed + light upper ·
  Wed: full rest (non-negotiable) · Thu: easy run + leg strength ·
  Fri: core + mobility (+ optional form drills: high knees, butt kicks,
  A-skips, 2×50m strides) · Sat: progressive long run · Sun: full rest /
  active mobility (non-negotiable)
- No recovery runs on rest days (running impact = 2.5–3× body weight)
- Daily 10-min head-to-toe mobility routine (see knowledge/mobility)
- Persona-level rule from the export: auto-scale down when high stress,
  >33°C heat, or joint/tendon pain logged; prioritize tendon/bone safety
  over volume; rest Wed/Sun are non-negotiable

**Phase 0 tasks:**
- [ ] User confirms race dates (Nov 1 2026 / Jan 24 2027) + registrations
- [ ] Confirm today's date is BEFORE Jul 27 2026 (program start) — if not, the
  block shifts and the calendar must be re-based
- [ ] Seed `training_phases` + `workout_plan` from `selmar_program.md` tables
- [ ] Freeze iteration-2 scope (this document)

---

## 3. Data Layer (Schema v2 + Migrations)

### 3.1 Migration system
- `schema_migrations` table; forward-only, numbered migration files (`migrations/001_init.sql`, …)
- `init_db()` applies pending migrations on startup
- New fields (sleep, HRV, strength details) = new migration, never a table rebuild

### 3.2 Core tables

```sql
-- v2 schema (superset of v1)
daily_logs (id, date, user_id, user_input, has_image, image_path,
            ai_response, rpe INT CHECK(1-10), fatigue INT CHECK(1-10),
            weight_kg, sleep_hours, session_type, completed INT,
            verified INT,                              -- user confirmed values
            persona_drafts JSON,                        -- audit: all 4 drafts + synthesis
            model_used, prompt_version, raw_payload)    -- audit trail

athlete_profile (user_id, height_cm, weight_kg, target_race, target_pace,
                 updated_at)                              -- mutable, via commands

training_phases (id, phase_name, start_date, end_date, focus,
                 volume_range, pace_target, rules_json)

workout_plan (date, day_type, session_type, description,
              prescribed_km, target_pace, notes)          -- /today reads this

weekly_rollups (week_start, volume_km, avg_rpe, avg_fatigue,
                weight_trend, completed_sessions, long_run_km)

kb_chunks (id, persona TEXT, title, source, content, embedding BLOB, created_at)
                                                            -- KB separated by persona

eval_cases (id, persona, prompt, expected_facts, expected_advice, last_result)

-- NEW: suggestion engine
suggestions_log (id, created_at, type, trigger, message, buttons JSON,
                 accepted INT, dismissed INT)             -- every push, audited

challenges (id, week_start, title, description, persona,
            accepted INT, completed INT, completed_at)    -- weekly challenges

target_history (id, created_at, target_pace, predicted_pace,
                source TEXT, confirmed INT)                -- /target + replan audit

performance_anchors (id, date, distance_km, time_sec, source TEXT,
                     verified INT)                         -- prediction inputs (best efforts/races)
```

### 3.3 Weekly rollups
- Computed from `daily_logs` every Sunday (or on-demand)
- Give the bot 5-month trends without giant prompts: `volume_km`, `avg_rpe`, `avg_fatigue`, `weight_trend`
- Lightweight version of the TrainingPeaks load model (CTL/ATL/TSB) — volume trend = chronic load, week delta = acute load

---

## 4. AI Engine

### 4.1 Structured extraction (accuracy #1)
- Free-text/image input → LLM extracts JSON: `{rpe, fatigue, weight_kg, session_type, notes}`
- **Pydantic validates**; on failure → one corrective re-prompt; second failure → ask user directly
- Out-of-range values rejected (RPE 1–10, fatigue 1–10, weight 30–200 kg)

### 4.2 Computed facts (accuracy #2)
- `facts.py` computes from DB: last-7-day RPE mean, fatigue trend, volume delta vs last week, weekly % increase, pace trends
- Injected into every persona pass as a **facts block** — personas reference these numbers, never derive them

### 4.3 Prompt composition (per persona — replaces prompt editing)
Each persona prompt = small immutable role core + per-request sections:
1. Role identity (versioned file, never edited inline)
2. Profile snapshot (from `athlete_profile`)
3. Current phase + today's workout (from calendar)
4. Computed facts block (from `facts.py`)
5. Persona's own KB retrieval (cited as `[SOURCE: title]`)
6. Persona guardrail rules (fixed file, versioned)

**Rule:** nothing with a shelf life is hardcoded. Prompt versions logged on every row.

### 4.4 Knowledge grounding (RAG — per-persona KB)
- `knowledge/` split by persona — **4 corpora**, each retrieved independently:
  - `runner/`: pacing strategy (7:06–7:10/km), HM training principles, ≤10% weekly volume rule, heat/humidity running (KL/Selangor)
  - `calisthenics/`: bodyweight progressions (push/pull/squat/core), 3x/week split, overload rules, strength↔running integration
  - `mobility/`: pre-run activation, warm-up/cool-down, quad/hip/ankle mobility, tightness routines
  - `physio/`: injury triage, red flags, quad tendonitis + shin splint rehab progressions, load management around injury, when to rest/see professional
- `ingest_kb.py`: sources → **MarkItDown** (free, local — PDFs, Word, HTML → clean Markdown; this is MarkItDown's real role) → chunk by heading → **local embeddings** (`sentence-transformers`, free, CPU — corpus is ~100 chunks; no embedding API needed) → `kb_chunks` (embedding BLOB, cosine in Python — no compiled extensions)
- Query per persona: embed input → top-k=4 → similarity threshold ≥0.7 → below: "no knowledge-base match" for that persona, stated explicitly
- **Chunks are advisory; computed facts always override them**
- KB edits → re-ingest + run eval gate

### 4.5 Guardrails (run BEFORE the AI, per persona)
- Physio red flags evaluated in code: acute injury symptoms, chest pain, fever+run, etc. → canned response (rest / see professional), **AI bypassed entirely**
- Hard caps in code: never >10% weekly volume increase; never recommend running through listed symptoms; strength progression rules (e.g., no added load through painful joints)
- User claims cross-checked: reported pace wildly off from stored runs → bot surfaces the discrepancy

### 4.6 Synthesis & conflict resolution
- `synthesize.py` receives 4 persona drafts + facts + hierarchy rules
- **Hierarchy:** physio (safety) > runner (load) > calisthenics > mobility
- Conflicts surfaced explicitly in the reply, never silently resolved
- Synthesis output validated: citations present, no number contradicts the facts block (code check)

### 4.7 LLM abstraction (provider-agnostic — DeepSeek primary)
- **Primary: DeepSeek-V4-Flash** (`deepseek-v4-flash`; OpenAI-compatible API, base_url `https://api.deepseek.com`, `openai` SDK). Cheap tokens make the 6-pass committee design affordable. Supports JSON output (extraction pass) + thinking mode with `reasoning_effort` (synthesis pass — reasoning where accuracy matters)
- `llm_client.py`: one interface; provider/model config in `.env`. OpenAI-compatible → swappable to Qwen, GLM, or local Ollama by changing base_url only
- **Vision is separate** — DeepSeek's API is text-only (no image input in their API docs). Two screenshot routes, config-swappable: **(a) default — fully free:** local OCR (EasyOCR/PaddleOCR, DL-based — best free local accuracy on stylized UI; Tesseract as lightweight fallback) → text → DeepSeek parses fields. **(b) accuracy upgrade:** vision LLM (Gemini Flash; ~1–2 calls/day, pennies). Same output contract, same validation chain (§5)
- **Embeddings are local** — `sentence-transformers` on CPU; no embedding API required (see §4.4)
- Fallback chain: `deepseek-v4-flash` → `deepseek-v4-pro` → **degraded deterministic mode** (schedule + last-3-days stats, no AI)
- Retry with exponential backoff + jitter on 429/5xx/timeout
- Model name + version logged per row (audit + regression detection)
- **Model swap = full eval suite re-run** (regression gate) — exactly what the harness exists for. Switching to a new DeepSeek release is a config change + gate pass, never a silent drift

---

## 5. Strava Screenshot Pipeline (accuracy-critical — the stated priority)

Screenshots are the bot's most error-prone input. Pipeline makes every number verifiable:

```
screenshot + caption
   │
   ▼
1. read pass          DEFAULT (free, no cloud): local OCR (EasyOCR/PaddleOCR)
                      extracts text → DeepSeek parses it into RAW fields
                      {activity_type, distance_km, moving_time_min, avg_pace,
                      elevation_m, avg_hr, date} → Pydantic range-checked.
                      ALT (accuracy upgrade, pennies): vision LLM (Gemini Flash)
                      reads fields directly. Same output shape, same validation.
   │
   ▼
2. math check (code)  pace_computed = moving_time / distance
                      vs pace_read by AI → diff > 5 s/km → field flagged UNCERTAIN
   │
   ▼
3. plausibility       distance 0.1–50 km; HR 30–220; time matches distance;
                      date within 48h unless caption says otherwise
   │
   ▼
4. plan comparison    vs workout_plan for that date:
                      actual vs prescribed distance, pace vs target pace
                      → deterministic deltas (fed into facts block)
   │
   ▼
5. echo & confirm     "Read: 5.02 km, 24:59 → 4:58/km. Planned: 5.0 km easy.
                      Correct?" → user confirms or corrects (one-shot)
   │
   ▼
6. store verified     verified=1; rollups updated only from verified rows
```

- **Never silently commit AI-read numbers** — unverified values are marked and excluded from stats
- **MarkItDown is *not* used for screenshots** (no document structure to preserve; its image OCR needs a cloud engine). It earns its place in KB ingestion only. Screenshots go straight to local OCR → DeepSeek parse
- Vision fails validation twice → ask user to type distance/time manually (text fallback)
- **Optional future:** Strava share-link / GPX import → zero-OCR accuracy; screenshots remain as fallback
- **Eval ground truth:** 10–20 real Strava screenshots (user's own) with known values — the test set for this pipeline
- Verified quality efforts (best 5K/10K etc.) feed `performance_anchors` — the prediction engine's inputs

---

## 6. Telegram Layer

### 6.1 One-tap UX (inline buttons)
Every suggestion and most commands render as **inline buttons** under the reply (`InlineKeyboardMarkup` + `CallbackQueryHandler`). User taps once — never types commands. Command suite below is the underlying API; buttons are the surface.

### 6.2 Command suite

| Command | What it does | Button contexts |
|---|---|---|
| `/start` | Quick-start + current phase + 4-persona intro | — |
| `/today` | Phase-aware workout for today | any suggestion about today |
| `/summary` | Weekly recap from rollups | Sunday push |
| `/log` | Guided logging (RPE, fatigue, weight, sleep) | after any run confirmation |
| `/weight` | Update profile weight | replan proposals |
| `/phase` | Current phase, dates, focus | phase-change reminders |
| `/personas` | Show the 4 expert perspectives | — |
| `/challenge` | Weekly challenge proposal (AI-personalized from templates) | Sunday push, milestone celebrations |
| `/predict` | Race-time prediction (Riegel formula, code-computed) | prediction updates |
| `/target` | View/update race target pace (never auto-changed) | replan proposals |
| `/trend` | Volume/fatigue/pace trends (text + optional chart) | any trend question |
| `/streak` | Consistency + streak stats | missed-session nudges |
| `/replan` | Run the milestone gate on demand | plan-drift suggestions |
| `/check` | Physio quick triage (structured symptom questions) | injury-watch suggestions |
| `/mobility` | Today's mobility routine (phase + symptom-aware) | tightness reports |
| `/strength` | Today's calisthenics session | strength questions |
| `/mute` | Snooze proactive pushes (1 day / 1 week) | — |

### 6.3 Handlers
- Text handler → extraction pipeline; Photo handler → Strava pipeline
- Auth: `ALLOWED_USER_IDS` middleware
- Callback handler routes all button taps
- **Sunday recap push** (retention): volume, trends, next-week preview, milestone celebration, **+ challenge proposal button**

---

## 7. Proactive Suggestion Engine

The bot coaches between messages — but under strict rules (design law #5).

### 7.1 Model: deterministic triggers, AI-written message
Triggers fire in **code** on computed facts (never on model intuition). The AI only writes the personalized framing. Every suggestion carries a concrete action + button.

### 7.2 Suggestion catalog

| # | Type | Trigger (code) | Action offered |
|---|---|---|---|
| 1 | **Weekly challenge** | Sunday recap; phase-appropriate template × persona (runner: hill strides; calisthenics: hold progression; mobility: daily-5 routine; physio: no-go zone checks) | [Accept] [Skip] → tracked in `challenges`, completion celebrated |
| 2 | **Prediction update** | ≥6 verified efforts AND pace trend shifted >3% | [See prediction] (/predict) [Update target] (/target) |
| 3 | **Recovery nudge** | fatigue trend ↑ 2+ weeks, or RPE high + quality run scheduled | [Swap today's run] [Log rest] |
| 4 | **Injury watch** | same symptom keyword in 2+ logs within 14 days | [Quick check] (/check) |
| 5 | **Session adjustment** | heat/rain logged, or weather source (free: open-meteo, no key) says >31°C / storm | [Adjusted plan] |
| 6 | **Milestone** | 50 km month, streak PR, race result, challenge completed | [Next challenge] (/challenge) |
| 7 | **Plan drift** | 2+ missed sessions in 10 days, or volume spike >10% | [Replan] (/replan) |
| 8 | **Phase boundary** | phase change in ≤7 days | [Show new phase] (/phase) |
| 9 | **Silence check** | no logs 3+ days (gentle, non-guilt, streak-aware) | [Quick log] (/log) |
| 10 | **Form check** (optional) | quarterly, or after injury return | [Send video] (vision pass) |

### 7.3 Anti-nagging rules (hard caps in code)
- Max **2 pushes/day**, max 1 before noon
- Quiet hours 22:00–07:00 (configurable)
- No pushes during taper week except phase reminders + race-day prep
- Every push has a one-tap dismiss; dismissed types don't recur for 7 days
- `/mute` snooze honored globally
- Suggestions only when there is a concrete action — no motivational spam
- In-response suggestions (button rows attached to a reply) don't count against the push cap

### 7.4 Race-time prediction (code-computed, AI-explained)
- **Math:** Riegel formula `T2 = T1 × (D2/D1)^1.06` (Runner's World 1977 / American Scientist 1981 — the industry-standard predictor used by Runner's World etc.)
- **Input:** best verified `performance_anchor` (race result preferred; else best effort from Strava-verified logs). Training runs never used — they over-predict
- **Validity:** only for efforts in Riegel's 3.5–230 min endurance range
- **Calibration:** after each race, the race result becomes the new anchor; with 2+ anchors the exponent is refit from the athlete's own data (`b = ln(T2/T1) / ln(D2/D1)`) — fixes the known 1.06 over-prediction bias for longer distances
- **Honesty:** output a range (±5%), never a single number; AI must state caveats (KL heat/humidity, course profile, consistency assumption)
- **Never auto-changes the target** — proposes via `/target`, user confirms

### 7.5 Eval additions (suggestion engine)
- Trigger unit tests: given a week of synthetic data, correct triggers fire, none fire spuriously
- Anti-nag tests: caps, quiet hours, dismissal dedup, taper silence — all enforced
- Prediction tests: Riegel math exact; prediction within tolerance of known ground truth; anchor calibration refit correct
- Button-flow tests: every suggestion's button routes to the right handler

---

## 8. Milestone Re-plan Gates (anti-stale)

Every 4–6 weeks, `replan.py` produces:
- Actual pace trend vs target → proposal: "last 4 weeks suggest 6:55/km — update target?" (user confirms, via `/target`)
- Volume progression vs ≤10% rule
- Weight trend vs target
- Strength progression vs plan (calisthenics persona input)
- Mobility/physio flags: recurring symptoms → propose physio review or KB update
- Prediction vs target gap → updated `/predict`
- Phase boundary check: is the calendar still right?
- Stale KB chunk report

Bot proposes; user confirms. **The goal stays honest because data drives it.** (Research note: Runna — the market leader — treats "tools to adjust your plan when you need to" as core, not optional.)

---

## 9. Retention Engineering (the non-code fracture)

- Sunday recap push with streak awareness + challenge proposal
- Milestone celebrations (first 50 km month, PR detection, challenge completions)
- Re-plan proposals framed as progress, not corrections
- Never guilt-trip missed sessions; adjust plan instead (per phase rules)
- Silence check is gentle and offers one-tap re-entry (`/log`)

---

## 10. Deployment

- `Dockerfile` (python:3.11-slim) + `docker-compose.yml` (bot + volume for SQLite + backups)
- Or `systemd` unit on the VPS
- Logging: `logging` module, rotation, structured level config
- Backups: daily SQLite copy (`sqlite3 .backup`), retention 30 days
- Env: `TELEGRAM_BOT_TOKEN`, `DEEPSEEK_API_KEY`, `VISION_API_KEY` (Gemini Flash for screenshots), `ALLOWED_USER_IDS`, `PRIMARY_MODEL=deepseek-v4-flash`, `FALLBACK_MODEL=deepseek-v4-pro`
- Optional weather source: open-meteo (free, no API key) for session-adjustment triggers

### Security (public GitHub repo — threat model)

**Architecture-level defense:**
- `ALLOWED_USER_IDS` allowlist is **the** gate: checked first in every handler, before any processing. Strangers get an immediate silent rejection — no LLM, no OCR, no DB access, no error detail. Prompt injection / OCR injection / data poisoning are non-issues externally because nothing external reaches the pipeline
- For the allowed user: user input stays in the "user message" role, never concatenated into system-prompt sections. OCR text treated as untrusted content, same delimiters
- Polling, no webhook → no public endpoint exists to attack

**Secrets hygiene (before git init):**
- `.gitignore` FIRST: `.env`, `*.db`, `uploads/`, `__pycache__/`, `eval/real/`
- `.env.example` committed with every var documented; real `.env` never
- Pinned deps (`==`, not `>=`) in requirements.txt
- Bot token: revoke via BotFather `/revoke` (old one was shared in chat) → new token only in `.env`, never in chat or git

**Public-repo data rules:**
- Health data (SQLite) never in repo
- Real Strava screenshots (contain run data: dates, distances, HR) NOT in public repo. Public eval suite uses **synthetic test images**; real screenshots live in gitignored `eval/real/`, README notes "user-provided, not in repo"

**Abuse hardening:**
- Debounce: max 1 message/second per user (timestamp check)
- Image cap: max 4096px dimension before OCR (else resize) — resource-exhaustion guard

**GitHub settings (user action):**
- Enable secret scanning + push protection (free for public repos)
- Enable Dependabot

**Logging:** never log tokens/keys; mask secrets; no secrets in error messages

---

## 11. Implementation Phases

| Phase | Deliverable | Done when |
|---|---|---|
| 0 | Calendar pinned, phases computed, scope frozen | Phase 0 checkboxes ✅ |
| 1 | venv, env, deps, migrations infra, `db.py`, `llm_client.py`, logging | `init_db()` applies migrations; client fallback works |
| 2 | extraction + validation, `facts.py`, weekly rollups | Malformed input → clean JSON or corrective prompt; rollup numbers correct |
| 3 | **Persona layer**: 4 role prompts, 4 KB corpora, ingest + per-persona retrieval, guardrails | Each persona retrieves its own chunks; physio red flags bypass AI |
| 4 | **Synthesis**: merge 4 drafts, conflict hierarchy, output validation | Conflict cases produce hierarchy-correct answers |
| 5 | bot.py handlers, **Strava pipeline**, `/today` phase-aware, inline buttons | Screenshot → verified log with code-computed pace; buttons route correctly |
| 6 | **Suggestion engine**: triggers, challenge templates, anti-nag caps, prediction (`/predict`, Riegel + anchors) | Trigger tests pass; prediction within tolerance; caps enforced |
| 7 | Eval suite (persona cases, conflicts, Strava set, retrieval, citations, triggers, prediction) | Full suite green; gate blocks bad changes |
| 8 | `replan.py` milestone gates, retention pushes | Gate produces correct proposal from real data |
| 9 | Docker/systemd, backups, monitoring | Restart survives; backup restores; 24/7 stable |

---

## 12. Verification (acceptance for v2)

1. **4-perspective answer:** send "tight right quad after yesterday's run" → reply covers load (runner), strength context (calisthenics), mobility routine (mobility), and symptom triage (physio) — as one coherent answer, with physio prioritized
2. **Conflict handling:** "quad tendonitis flare, long run scheduled tomorrow" → physio veto wins, conflict surfaced explicitly
3. **Strava accuracy:** screenshot of a 5.02 km run → bot reports code-computed pace; a doctored/inconsistent screenshot → bot flags UNCERTAIN and asks
4. **Structured accuracy:** "Work stress 8/10, hot 33C, tight right quad" → DB row has rpe=8, fatigue parsed, physio chunk cited, facts block reflects 7-day context
5. **Phase awareness:** during base phase, `/today` gives base work; after calendar advances, build work — no manual prompt edits
6. **Anti-stale:** after 6 weeks of logged runs, replan proposes a pace target matching actual trend — user accepts/rejects
7. **Hallucination check:** query with no KB match and no history → bot says "no data," does not invent
8. **Red-flag test:** "chest pain during run" → canned medical advice, AI bypassed
9. **Suggestion discipline:** a day with no triggers → zero pushes; a week of missed sessions → exactly one plan-drift suggestion, not five
10. **Prediction honesty:** `/predict` output is a ±5% range from a verified anchor, with caveats stated; never a single over-confident number
11. **Button flow:** every suggestion's button performs its action; dismiss works; `/mute` respected
12. **Migration test:** v1 DB → v2 migrations apply cleanly, no data loss
13. **Eval gate:** a deliberately bad prompt change fails the suite
14. **Degraded mode:** kill the API key → bot still answers schedule/stats from DB
15. **Persona pluggability:** adding a 5th persona (e.g., nutrition) = new config + KB + eval cases, zero pipeline code changes
