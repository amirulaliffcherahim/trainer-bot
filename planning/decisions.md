# Decisions

Locked decisions only — one entry per decision, with the "why". Until an
idea lands here it's still a candidate in brainstorm.md.

---

## 2026-09 — Athlete data comes from the Strava API, not micro-RAG
- The old per-persona micro-RAG corpus is **not** the athlete-data layer.
- trainer-bot pulls the athlete's real training data live from the Strava
  API (OAuth2, `activity:read` + `activity:read_all`, webhooks for updates).
- Why: real structured data (distance, time, HR, streams) is what plan
  generation and adjustment math need; retrieval of curated text snippets
  was a proxy for data we now get first-hand.
- The `knowledge/` corpus may later serve only as optional coach-content /
  "voice" material — separate concern, not a data source.
- Grounding: `knowledge/strava_api/strava_api_research.md`.

## 2026-09 — Single user: me (at least for now)
- trainer-bot is a personal tool: one athlete, my Strava account.
- Why: it starts as my own coach; "Single Player Mode" (Strava athlete
  capacity 1) needs no app review and no multi-user infra (auth, billing,
  per-user rate limits, hosting scale).
- If it later grows to family/friends, that's a deliberate second act
  (Strava upgrade → capacity 10 → review), not today's problem.
- Self-hosted, single-user storage (SQLite-style) is the natural fit.

## 2026-09 — VDOT stays live, auto-updated from my PBs
- Every Strava sync updates the VDOT engine from PB info in the pulled
  activities (best recent effort per distance ⇒ new VDOT ⇒ new paces).
- No manual "enter a race time" prompt required for day-to-day use.
- Why: the whole point of pulling real data is that the fitness anchor never
  goes stale — plan paces track me instead of waiting for a race.
- Grounding: `knowledge/vdot_engine/vdot_calculator_research.md`.

## 2026-09 — Feedback is captured, not assumed
- trainer-bot asks for feedback **only on newly pulled activities that are
  not yet flagged/rated** — old history is never re-interrogated.
- It also runs a **daily journal check-in** (how the day / body feels).
- Both feed plan adjustment (pace/volume/type of next sessions).
- Why: honest, low-friction input beats asking about stale workouts; the
  journal catches the fatigue/soreness/motivation that Strava numbers miss.

## 2026-09 — Calendar is the hub, and the plan is checked against Strava
- The app has a **calendar** (V.O2/VDOT-style plan calendar) showing planned
  sessions.
- A **plan-vs-actual matcher** compares Strava activities against the plan:
  for each planned session, did a matching activity happen that day
  (date/sport/distance tolerance)? Statuses: done / partial / missed / plus
  unmatched extra activities.
- Why: "did I actually do the training" is the ground truth the coach needs
  before it adjusts anything — feedback and adjustment hang off the matcher
  result, not off assumptions.

## 2026-09 — Plan horizon: current month, or the race when one is set
- With no goal event: the plan spans only the **current calendar month**
  (today → month end). With an upcoming race: the plan runs **through race
  day**, phasing build → taper → race (step-back weeks every 3rd week still
  apply inside race builds), then ~7 days of easy post-race recovery before
  normal progression resumes.
- Why: monthly windows stay reviewable and adapt to real volume each
  month; a race overrides the window so training never ignores the goal.
- Sessions stay effort-based (no per-session paces — earlier decision);
  "based on the race target" = horizon/phasing to the race + the race-day
  session carries the goal (predicted from VDOT when no target set).
- Grounding: advisor review 2026-09; `knowledge/runner/volume_progression.md`.
