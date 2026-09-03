# Brainstorm — trainer-bot, next generation

Living scratchpad. Append; never rewrite. Facts belong in `knowledge/`, plans
in `decisions.md` once locked.

---

## The one-line vision (draft)

> A single-user (me) coach in the browser: pulls my runs from Strava, keeps
> a **live VDOT** anchored to my PBs, asks me how workouts and days felt
> (feedback on new/unrated activities + a daily journal), and builds a plan
> from the **knowledge corpus** — race-aware when an event is coming.

## What we know already (context, not decisions)

### Product shape (specified so far, 2026-09)
- **One user: me.** Single Player Mode on Strava is fine; self-hosted;
  SQLite-style single-user storage.
- **Strava → VDOT, always current.** Every sync pulls activities; PB info in
  the new data updates the VDOT engine (no manual race-time prompts).
- **AI coach asks, doesn't assume.** Feedback is requested for newly pulled
  activities that have no flag/rating yet — old workouts are never
  re-interrogated. Input: how the workout felt.
- **Daily journal check-in.** The coach asks how the day/body feels (energy,
  soreness, sleep, mood, …) and factors it into plan adjustment.
- **Plan = knowledge rules + event status.** The plan is built from the
  curated `knowledge/` corpus (coaching rules), not LLM improv: if I have an
  upcoming event → event-targeted plan; if not → base/maintenance plan.
- **Look & feel is up for grabs.** The UI may borrow the visual language of
  the V.O2/VDOT app, Runna, Strava, or Adidas Running (see open Q below).
  Chosen mix (2026-09): Runna-led shell + VDOT numbers + Strava accents.
- **Calendar + plan-vs-actual (2026-09).** A V.O2-style calendar shows planned
  sessions; a matcher compares each planned session against Strava
  activities for that day → done / partial / missed (plus unmatched extra
  runs). Calendar is the hub where plan meets reality.

### End-to-end loop & MVP gaps (2026-09)
Loop: Strava sync (webhook + backfill) → activity store → **matcher** (plan
vs actual) → feedback/journal on new or missed items → **adjustment rules**
→ knowledge+event plan → calendar → repeat.

Missing / underspecified so far (open threads to close before build):
- [ ] **Matcher rules** — tolerance window for "same day" (local tz, not UTC),
      sport/type matching, distance tolerance for partial credit, multi-run
      days, what counts as extra (commute vs junk).
- [ ] **Event model** — manual goal-event input (date, distance, type); event
      → phase plan (base/build/peak/taper) from knowledge rules. Strava has
      no race-calendar API (see knowledge/strava_api).
- [ ] **Regeneration cadence** — when is the plan re-rolled: weekly roll?
      after missed/done days? on VDOT change? on event countdown milestones?
- [ ] **Adjustment rules** — hard rules from feedback: soreness → swap to
      easy/mobility; felt-effort ≫ planned → back off tomorrow; missed
      workout → reschedule or trim. Red-flag guardrails (physio triage,
      10% volume cap) gate everything.
- [ ] **VDOT anchor policy** — which distances, recency window, handling of
      easy-only weeks / treadmill / no-HR / hill runs.
- [ ] **Strava OAuth UX + token storage** — connect screen, callback URL,
      refresh-token rotation persistence (single user, SQLite).
- [ ] **Sync & deployment shape** — webhook needs a PUBLIC HTTPS callback;
      decide local-only vs home server vs VPS (old stack: Docker/PM2). If
      no public endpoint: single-user polling fits default rate limits
      (100 req/15 min non-upload) — matcher runs on each sync.
- [ ] **Notifications** — web push (PWA) vs only-when-open prompts for
      journal/rating/missed-workout nudges.
- [ ] **Plan content engine** — explicit mapping: which knowledge/ files feed
      which plan decisions (pacing, volume_progression, rest_day_rules,
      heat_humidity, triathlon weekly structures, physio red flags).
- [ ] **Data model doc** — entities: athlete, strava_account/tokens,
      activity, planned_session, match_result, feedback, journal_entry,
      event, vdot_snapshot, calendar_day.
- [ ] Plan coverage scope (Q2) still open — run-only v1? strength? tri?

### Data layer (user directive, 2026-09)
- **Micro-RAG is dead as the athlete-memory layer.** No per-persona knowledge
  retrieval driving athlete data — the app pulls the athlete's real training
  data **live from the Strava API** (OAuth2, activities, stats, streams,
  webhooks).
- The `knowledge/` corpus is NOT the data source anymore. It may survive only
  as optional coach-content/voice material later — separate concern.
- Full Strava API surface documented: `knowledge/strava_api/strava_api_research.md`.

### The old trainer-bot (deleted code, remembered architecture)
- Telegram bot + later web UI. Four expert personas ran in parallel
  (runner, calisthenics, mobility, physio) and an editor merged their
  answers — physio's advice won conflicts.
- Design law: **"The AI does the talking. The code does the math."** — pace,
  volume, fatigue computed deterministically; the LLM never did arithmetic.
- Micro-RAG: per-persona knowledge files, local embeddings, cosine top-k
  with threshold. No match → bot said "no data", never invented.
- Guardrails ran FIRST in code: red-flag symptoms, volume caps (10%/week),
  quiet hours, max suggestions per day.
- Feedback loops that existed: run reminders, Sunday recaps, milestone
  re-plan gates, coach suggestions; Strava sync via OCR then direct API.
- The knowledge corpus survived: `knowledge/` (runner, calisthenics,
  mobility, physio + added triathlon, nutrition).

### Product research already done
- `knowledge/vdot_engine/vdot_calculator_research.md` — full VDOT math:
  one effort (≥800 m) → VDOT → every training pace + equivalent race times.
  Deterministic, cheap, verified Python reference implementation included.

### Hard constraints stated so far
- Server-side web app, **accessible primarily from mobile browser**.
- Data source: **Strava API** (activities, profile) + personal info.
- Must take **feedback and adjust** the plan.
- VDOT-like score as the fitness anchor; Runna-like plan generation.

## Open questions (brainstorm these first)

1. **Who is the athlete?** [SETTLED 2026-09] Single user, me — Strava Single
   Player Mode, self-hosted, no multi-user infra (see decisions.md).
2. **What does the plan cover?** Run-only, run+strength, or full triathlon
   (swim/bike/run)? What event/goal distances matter (5K → marathon → 70.3)?
3. **VDOT inputs from Strava** — no race results? Can we derive VDOT from
   ordinary runs (recent best effort, heart-rate, GAP, critical speed)? Or do
   we prompt a "race"/time-trial first? Research done: **Strava has no
   cross-activity best-effort endpoint** — compute anchors from activity list
   (distance + moving_time, best recent effort per distance) or splits.
   VDOT-from-non-race data still needs its own study.
4. **Feedback mechanics** — what does "feedback" mean concretely?
   - After-workout felt-effort/RPE log? (old bot had this)
   - "Too hard / too easy / couldn't finish" per session?
   - Missed workouts (auto-adjust volume)?
   - Watch/HR data (Strava already gives HR, not just self-report)?
5. **Adjustment speed** — plan shifts weekly, or micro-adjusts next session
   (Runna-style "on pace? keep / slow down" mid-run is watch-side; we're
   browser-only). What's our unit of adjustment: day, week, phase?
6. **Plan engine vs LLM** — where does the LLM sit? (Old law: code does math,
   AI talks.) Generate plan structure in code from VDOT + periodization;
   LLM only writes explanations/copy? Or LLM proposes + code validates?
   Note: data layer is now pure API math — LLM has no role in ingestion.
7. **Mobile-browser UX & look** — direction chosen (2026-09): **Runna-led
   shell + VDOT/V.O2 data feel + Strava accents** (Adidas not selected).
   Drafted in `planning/design_reference.md`. Open micro-questions: per-type
   colours vs single accent, light vs dark, copy voice, chart approach.
8. **Scope of coaching smarts** — keep multi-domain (strength, mobility,
   physio triage, nutrition) or focus run/tri plan first? Knowledge corpus
   exists for all — reuse as the voice/advice layer?
9. **Race calendar / training phases** — Strava has no race-calendar API, so
   goal events are **manual input** (date, distance, type) → drives the
   event-aware plan; calendar hub is in scope (decided 2026-09). Still open:
   phase mapping rules and when re-planning triggers on event countdown.
10. **Data & privacy** — single-user self-hosted (SQLite like old bot) vs
    hosted multi-user (Postgres)? Strava tokens per user; refresh handling.

## Open ideas (capture all, judge later)
- [ ] "Coach on a card" — daily plan renders as one scannable mobile card
      (what, why, paces as mm:ss, linked to today's weather).
- [ ] VDOT trend chart from rolling best efforts — "you're 0.4 fitter than
      3 weeks ago".
- [ ] Strava webhook (activities.push) → auto-plan-feedback on new activity,
      no polling.
- [ ] Let the plan re-roll itself when life happens: "travel week" mode,
      "sick week" mode (old bot had rest-day rules + physio veto).
- [ ] Auto-detect hard/easy days from Strava HR data instead of trusting
      self-report.
- [ ] Reuse the 4-persona committee as the "coach voice" that explains the
      plan and answers questions about it.
- [ ] **Strava webhooks for plan feedback** (activity create → auto-import +
      compare vs today's planned session → adjust tomorrow) — no polling,
      rate-limit friendly (Strava's own recommendation).
- [ ] UI vibe anchors: VDOT tables / Runna cards / Strava feed / Adidas
      metrics — collect real screenshots + design notes before we pick
      (flag: needs visual research, not prose guessing).

## Active threads
- **Scope / no-event plan / weather & safety / race-day** — drafted in
  `planning/scope_weather_race.md` (2026-09). Candidates, not locked.
- Coach voice & chat — user declined for now; stays parked (S5 in the scope
  doc).

## Parked [RESEARCH] threads
- [x] Strava API surface (auth/scopes/rate-limits/webhooks/endpoints) — DONE:
      `knowledge/strava_api/strava_api_research.md`.
- [ ] How Runna structures a week/plan (session types, progression rules,
      adjustment triggers) — need source study before we copy anything.
- [ ] VDOT from non-race data — what's credible, what's snake oil.
- [ ] Visual references: V.O2 app, Runna, Strava, Adidas Running — capture
      screenshots/design language (palette, layout, components) into a
      design reference before choosing our look.
