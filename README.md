# trainer·bot

Single-user (me) running coach in the browser: pulls runs from the Strava
API, keeps a live **VDOT** anchored to best efforts, plans training weeks
from the knowledge corpus, and checks the plan against what was actually run.

Mobile-first web app (SvelteKit, server-rendered + minimal hand CSS).
Data lives in local SQLite (`trainer.db`); no cloud besides Strava itself.

## Features (shipped slices)

- **S1 — Data + VDOT.** Strava OAuth (refresh-rotation safe), paged backfill,
  PB scan (1 mi → marathon buckets) → VDOT + training paces + equivalent
  races. Fitness screen.
- **S2 — Plan + Calendar + matcher.** Knowledge-rule weekly plan generator
  (base mode + event/taper mode), 14-day plan calendar, plan-vs-actual
  matching (done / partial / missed / extra) from Strava activities.
- S3 (feedback/journal), S4 (race-day flow) — planned, not built.

## Run locally

```bash
npm install
cp .env.example .env      # add STRAVA_CLIENT_ID / STRAVA_CLIENT_SECRET
npm run dev               # http://localhost:5173
```

Register the API app at <https://www.strava.com/settings/api> and set the
**Authorization Callback Domain** to the host you run on (`localhost` is
whitelisted). New apps run in Single Player Mode (capacity 1) — enough.

## Scripts

| command | what |
|---|---|
| `npm run dev` | dev server |
| `npm test` | vitest (VDOT engine anchors, plan invariants, matcher) |
| `npm run check` | svelte-check + typecheck |
| `npm run build` | production build (adapter-node) |

## Repo map

- `src/lib/vdot.ts` — VDOT engine (port of the vdoto2.com algorithm;
  research + math in `knowledge/vdot_engine/`)
- `src/lib/server/` — db (node:sqlite + migrations), strava client,
  token store, sync, fitness, plan generator, matcher
- `knowledge/` — coaching content + product research
- `planning/` — product brainstorm, decisions, design, deploy runbook

## Deploy

See `planning/deploy.md` (pm2 + Cloudflare tunnel, port 4040).
