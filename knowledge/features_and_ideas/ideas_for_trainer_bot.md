# Ideas for trainer-bot — synthesized backlog

Synthesis of `runna_app_features.md`, `runna_training_hub.md`, `strava_features.md`,
`vdoto2_app_features.md` (2026-09). Research folder — NOT coach KB.
Priority = P0 (small, high value) → P2 (larger/new deps). Cross-check any
coaching number against `knowledge/runner/` before encoding into the generator.

## Already shipped (matched during research)

- 5-tab IA (Today/Plan/Activity/Fitness/Settings) ≈ Runna's Today/Plan/Activities.
- Plan-vs-actual statuses (Completed/Modified/Missed/Extra) ≈ V.O2 planned-vs-completed.
- Effort-based sessions (RPE) ≈ Runna RPE mode.
- Race goal w/ taper + pacing plan ≈ V.O2 equivalent performances + Runna taper.
- Per-activity AI review + effort log ≈ Runna Workout Insights.
- Elevation/pace charts + route map ≈ Strava activity analysis (lighter).

## P0 — quick wins (no new dependencies)

- Weekly mileage line on Today tab (Runna Today card) — one SQL sum.
- "New PR recalibrates" banner on race/fitness pages when the anchor changes
  (Strava goals-on-activities pattern; we already re-anchor on best effort).
- VDOT-over-time chart on Fitness (V.O2 stats) — data exists in fitness history.
- Consistency card: Completed/Modified/Missed counts this week + last 4 weeks
  (V.O2 consistency; derived from matcher output already produced).
- "Spend by zone" — planned minutes per intensity (easy/tempo/speed/long) for
  the visible plan window (V.O2 Your Paces) → answers "am I training the right
  paces for my goal".
- Missed-run escalation: after 3+ misses show a "get back on track" card
  offering skip/rearrange/rebuild (Runna Plan Realignment; matcher feeds it).
- ICS calendar export of the plan (V.O2 via Garmin; we can emit .ics directly)
  — dependency-light, pushes the plan into the user's own calendar.

## P1 — medium (data or logic work, no external services)

- Long-run archetype rotation: unstructured / progression / blocks /
  race-pace practice instead of one generic effort long run (Runna hub).
  Needs generator upgrade + session-type field.
- Hard-coded progression guardrails: ≤10%/wk volume rise, deload every 4–5
  weeks, volume-before-intensity phase separation, per-ability long-run cap
  (Runna hub). Partially present via knowledge rules — make them invariants.
- Frequency-scaled easy:hard mix (80:20 at 5–7 runs/wk; ~60:40 at 2–3/wk)
  derived from chosen run days (Runna hub).
- Effort-day caveat: RPE sessions are excluded from any pace-vs-target
  analysis (Runna) — document in pace-insight UI if we build one.
- Manual "link activity → planned session" on the plan (Runna) — matcher
  currently reconciles by date+distance only; allow explicit override.
- 30-min threshold time-trial suggestion to recalibrate VDOT when anchor is
  stale (~6 weeks unchanged, V.O2 prompt) — we have VDOT math + plans.
- Activity "top results" strip: per-run headline of what it meant vs goal/PR
  (Strava) — light NLP over existing review points.
- Race-pace range bands + sectioned negative-split guidance on race page
  (Runna: ±3–4 s/km around goal; already have goal pace).

## P2 — larger (new integrations or redesigns)

- Weather-aware pacing: Adapt-for-Heat rule (≈15–30 s/km slower per 5°C above
  15°C) with an hourly-forecast feed adjusting Today's session (Runna). Needs
  weather API key + session-shape adjustments (time-based easy runs in heat).
- Fitness & Freshness (Strava impulse-response model) over the plan calendar
  — readiness layer; real modelling effort.
- Performance predictions cross-check (Strava ML) — we have VDOT equivalents
  already; a pure-data prediction would be secondary signal.
- 14 benchmark PR auto-detection (Strava Best Efforts) replacing/augmenting
  single best-effort scan — more scan work but no new deps.
- Instant/manual workout with goal-based builder (Runna), logged without
  touching the stored plan.
- Structured strength + cross-training sessions in the calendar (V.O2) — our
  KB has calisthenics/mobility content to anchor plans.
- Age-graded levels / age-group rank (V.O2) — motivational; small feature.
- Watch delivery of sessions / manual GPS upload (.fit/.tcx/.gpx) — stretches
  past Strava as source of truth.

## Explicitly out of scope (noted for completeness)

- Social: kudos, feeds, clubs, group challenges (Strava) — single-user app.
- Community age-rank leaderboards — would need a community DB.
