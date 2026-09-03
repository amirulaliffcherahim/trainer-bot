# Build start — prerequisites & first steps

Ordered path from zero to a running trainer-bot. Status tracked here.

## Step 1 — Register the Strava API application (YOU, in browser)
- Go to https://www.strava.com/settings/api → "Create Your Application".
- Suggested values:
  - Application Name: `trainer-bot`
  - Category: Health & Fitness
  - Website / Logo: optional for personal use
  - **Authorization Callback Domain:** `localhost` for local dev
    (Strava whitelists localhost/127.0.0.1); switch to the real host once
    deployed.
- After save: note **Client ID** and **Client Secret** (store the secret
  only in a local env file — never in git).
- New apps start in Single Player Mode (capacity 1 athlete = me) — fine.
- ⏳ Status: pending — needs the user's Strava account action.
- ☐ Done — client_id/secret saved to local env

## Step 2 — Scaffold the web app (S1: Data + VDOT)
- ☑ Scaffolded (2026-09): SvelteKit (Svelte 5 runes) + adapter-node +
  node:sqlite (no native builds), hand CSS, no UI framework.
- ☑ VDOT engine ported + anchored tests: src/lib/vdot.ts / vdot.test.ts
  (vitest — run `npm test`).
- ☑ DB (trainer.db) + migrations: strava_token, activities, vdot_snapshots.
- ☑ OAuth routes (/api/auth/strava → callback) w/ refresh rotation;
  status/sync/fitness APIs.
- ☑ Mobile-first shell: Today / Fitness / Settings; Strava connect flow.
- ⏳ Needs: real STRAVA_CLIENT_ID/SECRET in .env (Step 1), then first sync.

## Step 2b — S2: Plan + Calendar + matcher (2026-09)
- ☑ Migration v2: events + planned_sessions (paces stored s/km; match status
  computed at read).
- ☑ plan.ts: deterministic generator — 28-day volume anchor (floor 18 km),
  Wed+Sun rest rule (rest_day_rules.md), Tue threshold 88% VDOT, Sat long
  25–35%, ≤10%/wk cap + sanity ceiling, step-back every 3rd week, event
  phases + taper (75/55/35 easy-only race week), race-day row w/ predicted
  goal, no-VDOT sessions carry "no anchor" labels (no invented paces).
- ☑ match.ts: local-date keying, 90/50 done/partial/missed, rest-day +
  second-run extras, trainer/manual/commute ignored.
- ☑ APIs: GET /api/plan, POST /api/plan/generate (replace-window),
  events GET/POST/DELETE (one active event rule).
- ☑ Plan tab UI (14-day list, status tags, event form + countdown) + Today
  shows today's planned session with match status.
- ☑ Tests 26/26 (vdot + plan + matcher), svelte-check 0, build clean,
  deployed & verified live on :4040.
- ☑ Interval sessions scheduled in event build weeks (Thu, 97.5% VDOT);
  none in base/taper. Tests now 28/28.
- ☑ Hourly auto-sync running in-app (first request starts the loop;
  verified [sync-hourly] log lines). Backfill window = start of year.

## Step 3 — S3: feedback + journal + adjustment (2026-09)
- ☑ Activity tab with rule-based AI review (VDOT zone classification) +
  feedback capture (felt / RPE 1–10 / soreness / note) per unrated activity.
- ☑ Plan wizard asks first (build & renew): training days, hard days + which
  days, goal race category + date → plan_prefs drives the generator.
- ☑ Daily journal table (migration v4) + check-in card on Today
  (energy/sleep/soreness/note).
- ☑ Adjustment engine (src/lib/server/s3.ts, pure): sharp→rest today +
  easy tomorrow; noticeable→easy 60%; low energy→easy 70%; felt hard
  (RPE≥8)→back off tomorrow; missed→never double up; <6h sleep→easy 80%.
  Applied at plan generation; coach note rendered on Today.
- ☑ 36/36 tests (vdot + plan + matcher + s3), check clean, deployed live.

## Step 4 — S4: race-day product (2026-09)
- ☑ Race briefing engine (src/lib/server/race.ts, pure): goal time/pace
  (explicit target or VDOT-predicted), negative-split plan, taper rows
  (75/55/35, race week easy-only), fuel & hydration plan, post-race
  checklist (KB-cited throughout).
- ☑ GET /api/race + /race prep page; Plan banner links "Race prep →".
- ☑ Verified against the live goal race (Selmar 21 km, 59 days out) —
  prediction 2:23:49 @ 6:51/km from VDOT 29.1. Tests now 40/40.
- ⏳ Blocker for real data: current Strava token scope is `read` only — needs
  re-consent with activity:read (see deploy.md go-live checklist).

### Legacy draft (superseded by the checkboxes above)

## Step 3 — Plan + Calendar + matcher (S2) then Feedback (S3), Race (S4)
See planning/scope_weather_race.md for slice definitions. Not started.

## Open blockers before Step 2
- Deployment/sync shape: local-only (polling sync is fine under rate
  limits) vs public HTTPS (enables webhooks). Doesn't block registration or
  local dev.
- Web-stack choice (framework) — next brainstorm item when starting S1.
