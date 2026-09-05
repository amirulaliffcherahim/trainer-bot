# Runna training hub — coaching-method ideas for the plan engine

Source: Runna Training Hub collection, crawled 2026-09. Numbers copied exactly.
Research folder — NOT coach KB. Cross-check against our knowledge/ corpus before
encoding any rule into the generator.

## Weather-aware pace adaptation

- "Adapt for Heat" adjusts pace targets per forecast hour so the session keeps
  the same training benefit.
- Rule of thumb: slow ~15–30 sec/km per 5°C above 15°C (e.g. 5:30/km easy
  becomes 6:00–6:15/km at 30°C).
- Heat: HR runs 10–20+ bpm higher; cardiac drift is normal. Humidity: sweat
  1–2 L/hr; easy runs can convert to time-based ("run 30 min, ignore
  distance"); extreme heat → fewer reps / longer recoveries.
- Fit: we have effort-based sessions but no live weather feed adjusting pace
  or session shape. Candidate: hourly forecast hook on Today/Plan.

## Four long-run archetypes

- Long runs rotate between: unstructured (zone 2, no pace targets),
  progression (pace rises in blocks, e.g. every 3 km), blocks (easy + steady
  zone 3), race-pace practice (goal-pace intervals on tired legs).
- Progression runs train negative-split skill; hardest work ends the run.
  Example: coach raced marathon 3–8 s/km faster than her training pace and
  still PB'd.
- Fit: our "effort long run" is generic — add typed long runs + rotation
  logic to the generator.

## Long-run sizing + deload cadence

- Long run grows 10–15% week-on-week; deload week every 4–5 weeks.
- Marathon: build to ~32 km (~20 mi) at least once; two 32 km runs = best
  results. >14-week plans bank more long runs than ≤13-week plans.
- Injury note: longer long runs raise injury risk; experienced runners cap at
  one (max two) runs beyond 20 mi.
- Fit: generator needs explicit deload cadence + per-ability long-run caps.

## Build weeks & the ~10% rule

- ~70% of running injuries stem from overuse/training errors. Weekly mileage
  rises at most ~10% (20 mi → no more than 22 mi).
- Never raise volume and intensity in the same week — add mileage first, then
  swap an easy run for tempo/interval. Cardio adapts faster than
  tendons/bones.
- Block rhythm: build, build, deload; build weeks shown in a mileage graph.
- Fit: progression logic exists; hard-code the 10% cap and volume/intensity
  phase separation.

## Frequency-scaled 80:20

- 5–7 runs/week → 4–5 easy, 2–3 hard (≈80:20).
- Only 2–3 runs/week → "60:40 split is more realistic" (1 easy + 1–2 hard).
- Warm-ups / cool-downs / jog recoveries don't count toward the hard 20%.
- Fit: derive easy:hard ratio from days-per-week, not a fixed 80:20.

## Auto re-baselining (Pace Insights)

- After each speed session compare achieved pace vs target: Pace on Point /
  Ahead of the Pack / Let's Review Your Pace / Variable Pace Detected.
- Accepting a recommendation shifts pace targets plan-wide. Manual edits:
  adjust estimated race time 20–30 s at a time.
- Fit: our VDOT anchor is static until the next best effort — add
  "ahead of target" detection → incremental pace re-baseline.

## Taper playbook

- Taper begins after the final race-practice long run, ~3 weeks out; week 1
  ~30% volume down, final week up to ~50% down; keep sharp "taper interval"
  sessions.
- Don't cram a missed long run within 7–10 days of race day.
- Strength: drop heavy lifts (squats/deadlifts/hip thrusts) 2 weeks out; skip
  the gym entirely in the final 5 days. Avoid new mobility work (DOMS risk).
- Fit: we have taper rows (75/55/35%) — verify against 30%/50% guidance and
  add strength taper rules.

## Race-time prediction & pacing ranges

- Prediction assumes relatively flat road course + good conditions.
  Example: 3:30 marathon → 4:58/km average, coach range ±3–4 s (4:55–5:03);
  negative split, first half no faster than 5:03/km; gel every 30–35 min
  (~60 g carbs/hr).
- Fit: VDOT pacing anchors exist; add race-pace range bands + sectioned
  negative-split guidance (partially in race page already).

## RPE as intensity mode

- Modified Borg 0–10. Runna prefers RPE over pace in heat, wind, humidity,
  hills, trails, altitude, fatigue, post-illness.
- Easy run = RPE 3–4/10, conversational, ≈ zone 2 / 60–70% max HR. Easy runs
  routinely feeling 6–7/10 usually means they've become something harder.
- RPE workouts are excluded from Pace Analysis (no comparable metric).
- Fit: effort sessions exist; add explicit "no pace analysis on RPE days".

## Threshold vs interval vs tempo taxonomy

- Interval = structure (reps + full recovery). Threshold = principle
  (~80–90% max HR, zone 4). VO₂-max intervals (shorter, harder) suit 5K;
  threshold reps suit distance.
- Field threshold test: 30-min time trial, average of final 20 min =
  threshold pace (60-min TT for experienced).
- Fit: our tempo/threshold sessions need zone anchors + optional time trial
  to recalibrate the VDOT start point.

## Plan-length presets & beginner arc

- Recommended minimums: New to Running 8 wk · Returning 6 wk · 5K 8 wk ·
  10K 10 wk · Half 12 wk · Fast-Track Half 8 wk · Marathon 16 wk ·
  Fast-Track Marathon 12 wk · Ultra 16 wk. Custom: 6–26 weeks.
- Beginner arc: walk-run → continuous time-based runs → "transition week"
  switches to distance-based 5K training. New-to-Running plans use time, not
  paces.
- Fit: fixed min-week presets per distance + explicit time→distance switch
  for true beginners.

## Source URLs

- https://support.runna.com/en/collections/3431932-training-hub
- https://support.runna.com/en/articles/13729841-what-is-an-easy-run
- https://support.runna.com/en/articles/9551650-80-20-training-principle
- https://support.runna.com/en/articles/6967043-what-is-rpe
- https://support.runna.com/en/articles/6576215-top-tips-for-tapering-before-a-race
- https://support.runna.com/en/articles/6969916-how-to-pace-a-marathon
- https://support.runna.com/en/articles/8608203-is-my-workout-a-threshold-interval-session-or-tempo-run
- https://support.runna.com/en/articles/15013260-what-is-a-build-week-understanding-progressive-overload-in-your-running-plan
- https://support.runna.com/en/articles/13868246-how-to-increase-your-running-mileage-safely
- https://support.runna.com/en/articles/10854865-what-are-pace-insight-recommendations-and-how-do-they-work
- https://support.runna.com/en/articles/6312562-top-tips-for-running-in-the-heat
- https://support.runna.com/en/articles/13928419-top-tips-for-running-in-humidity
- https://support.runna.com/en/articles/15959777-what-is-a-transition-week
- https://support.runna.com/en/articles/6262165-the-importance-of-a-deload-week
- https://support.runna.com/en/articles/8975787-how-long-should-i-make-my-runna-training-plan
- https://support.runna.com/en/articles/9813914-how-to-adjust-your-strength-training-ahead-of-your-race
- https://support.runna.com/en/articles/9144831-how-is-my-long-run-distance-calculated-in-my-marathon-plan
- https://support.runna.com/en/articles/9357249-understanding-the-long-runs-in-your-runna-plan
- https://support.runna.com/en/articles/6251445-how-is-my-target-race-time-predicted
