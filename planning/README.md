# planning/ — trainer-bot design brainstorm

Home for the extended brainstorming on what the next trainer-bot should look
like and how it should operate. Everything here is fluid — no decisions are
locked until we say so.

## Layout

| File | Purpose |
|---|---|
| `README.md` | This index + how we run the brainstorm |
| `brainstorm.md` | The living scratchpad — context we know + open questions |
| `decisions.md` | Locked decisions (created once we start agreeing) |
| `scope_weather_race.md` | Drafts: MVP slices, no-event plan, weather/safety, race-day |
| `design_reference.md` | Look & feel direction (Runna/VDOT/Strava mix) |
| `build_start.md` | Prerequisites + first build steps (Strava app registration etc.) |
| `deploy.md` | Server runbook: pm2, Cloudflare tunnel, Strava callback domain |

## How we brainstorm (rules)

- **Capture, don't judge.** Wild ideas go in `brainstorm.md` under Open Ideas.
  No idea is "too big" during capture.
- **One running doc, dated entries.** We append; we don't rewrite history.
  Every entry gets a date so we can see the thread evolve.
- **Separate questions from answers.** Big open questions live at the top of
  `brainstorm.md`; candidate answers accumulate under them.
- **Escalation path:** idea → discussed → agreed → moved to `decisions.md`
  with a one-line "why". Until then it stays a candidate.
- **Grounding:** claims about how something works (VDOT math, Strava API,
  pacing rules) get checked against `knowledge/` — facts live there, not here.
- **Scope discipline:** when a brainstorm thread needs deep research (e.g.
  "how does Runna structure weeks?"), it gets flagged `[RESEARCH]` and parked
  until we study it — we don't guess in the plan.

## Current state

Seed context written. First brainstorm session ready to run — start with the
open questions at the top of `brainstorm.md`.

## Sibling folders

- `knowledge/` — curated facts: coaching content (runner, calisthenics,
  mobility, physio, triathlon, nutrition) + product research
  (`vdot_engine/` — decoded VDOT calculator math).
