# Features & Ideas — product research

Competitive feature/UX reference for trainer-bot, crawled from coach-app support
sites (2026-09). Research namespace — **NOT coach KB**: do not wire a persona;
keep out of RAG (same rule as `vdot_engine/`).

## Files

| File | Source | Focus |
|---|---|---|
| `runna_app_features.md` | Runna support (app features) | Info architecture + UX patterns: Today card, Instant Workouts, Plan Realignment tray, Training Calendar, Pace Insights, AI briefings, Runna Score |
| `runna_training_hub.md` | Runna Training Hub | Coaching methods to encode: heat pace math, long-run archetypes, deload cadence, 10% rule, 80:20 by frequency, taper, RPE, plan lengths |
| `strava_features.md` | Strava support | Stats/activity features: Best Efforts, zones, Relative Effort, Fitness & Freshness, Predictions, goals, monthly recap |
| `vdoto2_app_features.md` | V.O2 support | VDOT-app features: accuracy scoring, stats, planned-vs-completed, paces, age rank |
| `ideas_for_trainer_bot.md` | synthesis | Prioritised candidate backlog mapped to what we already ship |

## How to use

- Grab ideas: read the synthesis first, then the per-source file for detail.
- Before encoding any coaching RULE into the plan generator, cross-check the
  number against our `knowledge/runner/` corpus (authoritative coach content).
- UI/UX ideas are app-behavior decisions — log them in `planning/decisions.md`
  or a new issue when picked up.

## Wiring status

| Folder | Persona | Retrievable by bot? |
|---|---|---|
| `features_and_ideas/` | — | ⛔ product research — no persona (like `vdot_engine/`) |
