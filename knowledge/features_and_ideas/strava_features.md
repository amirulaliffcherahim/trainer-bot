# Strava — feature & stats reference

Source: Strava support (Intercom), crawled 2026-09. Research folder — NOT coach KB.
Topics: Activity Analysis & Stats, Segments, Community. Social features noted as
low-fit for a single-user coach app.

## Auto Best Efforts (PR detection)

- Auto-tracks running PRs at 14 benchmark distances 400 m–50 K; top-3 lifetime
  + top-10 annual per distance, trend graph, per-run "fastest mark".
- Uses elapsed time (not moving); effort can be edited with a manual chip
  time or removed — next-fastest becomes the PR.
- First-ever distance isn't flagged as a PR (no prior baseline).
- Fit: our VDOT anchor scans best efforts already; borrow automatic PR
  detection + banner flags on PR runs.

## Activity "top results" module

- Web activity page shows a curated 3–4 top results: goals met, segment
  top-10/KOM, Best Efforts — the best story of the run.
- Fit: headline stat strip per activity ("what this run meant vs your plan").

## Race splits & pace analysis

- Tag an activity "Race" → pace bar-graph of fluctuation, mile/km trend,
  "meaningful splits" (e.g. 5K splits inside a marathon), scrub any moment,
  live projected finish time.
- Fit: planned-vs-actual split comparison for goal-race runs.

## Elevation profile with metric overlay

- Elevation chart visualises climbs/descents; overlay pace/HR/cadence to see
  where hills cost time.
- Gain from barometric file or GPS-vs-elevation-basemap lookup; smoothing +
  outlier discard.
- Fit: we have elevation + pace charts and a map — add overlay or sync axes.

## Heart rate chart & zones

- BPM line chart (avg/max) overlaid on elevation; % time in zones 1–5; max HR
  default 220 − age.
- Fit: intensity histogram + effort colouring per run (only when HR present).

## Training zones incl. pace zones

- HR (5), power (7), run-pace (6) zones; run-pace zones set from a recent race
  result. Grade Adjusted Pace (GAP) flattens hills. Zone-time breakdown; view
  over 7 d–1 yr or custom, per sport.
- Fit: derive pace-zone bands from VDOT + race goal to colour plan sessions.

## Relative Effort + weekly load graph

- Cardio-load score from HR or Perceived Exertion (RPE), personalised to own
  HR zones, comparable across sports and distances.
- Weekly cumulative graph with a white "suggested range" band = 3-week
  average; aim above/below/in range; week-over-week trend.
- Fit: per-run effort vs planned intensity; weekly load gauge on Fitness.

## Fitness & Freshness

- Fitness, Fatigue, Form lines over time from Training Load / Relative Effort
  via an impulse-response model (Banister/Coggan).
- Races marked red; click a point for the exact date value; click again for
  contributing activities + impulse; 7-day fitness delta shown.
- Fit: readiness/trend layer over the plan calendar.

## Performance Predictions

- ML model (100+ athlete attributes) estimates 5K/10K/half/marathon from ≥20
  runs in a rolling 24 weeks; recomputed per upload and after 3 quiet days.
- Prediction history over 1/3/6 months; each distance independent.
- Fit: cross-check VDOT-derived targets against data-driven predictions.

## Goals with progress on activities

- Distance / time / activity-count / elevation goals over week/month/year;
  progress shows on the Progress tab AND on activity pages; suggested goals
  when none set.
- Fit: borrow the pattern — a plan run shows how it moved you toward the race goal.

## Progress Summary Chart

- Totals (distance, time, elevation, count) per sport over 1W/1M/3M/6M/YTD/1Y;
  tap a week to drill into contributing activities; compare date ranges.
- Fit: volume/consistency trend per training cycle.

## Month in Sport recap

- Auto monthly report: active days, trophy case, totals card, social card;
  shareable/downloadable; needs ≥3 activities; mobile-app-only.
- Fit: monthly digest over plan data.

## All-Time PRs (manual curator)

- Manually entered fastest official-race/verified times on profile, linkable
  to an activity or race result; complements auto Best Efforts.
- Fit: let user pin verified race PRs alongside the VDOT goal.

## Segments & effort comparison

- Community-created course sections; runs auto-match, earning effort +
  achievements; leaderboards rank times (top-10 free).
- Effort Comparison replays up to 4 of your efforts as map pins + time-gap
  chart vs a baseline, 20 s virtual-race playback (web).
- Fit: leaderboards are social/overkill; "own-history on repeated routes"
  comparison transfers (same route, effort v effort).

## Challenges & trophies

- Time-boxed goals (distance/elevation/time/active-days, single or
  cumulative); challenge gallery, join, progress bar, leaderboard, Trophy
  Case of completion badges.
- Fit: adapt progress-bar + badge pattern for plan-completion streaks.

## Kudos / feed (social — low fit)

- One-tap kudos, comments, mentions, feed. Single-user coach app does not need
  it — noted for completeness only.

## Other features seen (lower fit)

- Activity Split Tool (data hygiene), 3D map layer, flyover/replay, heatmaps,
  club group goals/leaderboards, Group Challenges.

## Source URLs

Collections:
- https://support.strava.com/en-us/
- https://support.strava.com/en-us/collections/19657597-activity-analysis-and-stats
- https://support.strava.com/en-us/collections/19657604-segments-and-routes
- https://support.strava.com/en-us/collections/19657598-clubs-challenges-and-community

Articles:
- https://support.strava.com/en-us/articles/15401661-best-efforts-running
- https://support.strava.com/en-us/articles/15401569-training-zones-on-strava
- https://support.strava.com/en-us/articles/15402032-fitness-freshness
- https://support.strava.com/en-us/articles/15401794-relative-effort
- https://support.strava.com/en-us/articles/15401591-performance-predictions
- https://support.strava.com/en-us/articles/15402021-your-activity-s-top-results
- https://support.strava.com/en-us/articles/15402041-all-time-prs
- https://support.strava.com/en-us/articles/15401842-activity-split-tool
- https://support.strava.com/en-us/articles/15401945-strava-segments
- https://support.strava.com/en-us/articles/15401771-segment-leaderboard-filters
- https://support.strava.com/en-us/articles/15401916-strava-challenges
- https://support.strava.com/en-us/articles/15402054-what-is-kudos
- https://support.strava.com/en-us/articles/15401618-progress-summary-chart
- https://support.strava.com/en-us/articles/15401694-goals-on-the-strava-app
- https://support.strava.com/en-us/articles/15401741-month-in-sport
- https://support.strava.com/en-us/articles/15402116-run-pace-zone-analysis
- https://support.strava.com/en-us/articles/15401762-heart-rate
- https://support.strava.com/en-us/articles/15401909-elevation
- https://support.strava.com/en-us/articles/15402094-effort-comparison
- https://support.strava.com/en-us/articles/15401736-group-challenges
