# Runna app — features & UX reference

Source: Runna support site (app-features collection + nav guide), crawled 2026-09.
Purpose: borrowable product/UX ideas for trainer-bot. Research folder — NOT coach KB.

## App structure (info architecture)

- Five bottom tabs: **Today** · **Plan** · **Activities** · **Profile** · **Support**.
- Today = today's workout card, weekly mileage total, Instant Workouts entry,
  Plan Adjustment tray (appears when sessions are missed).
- Plan = full plan/calendar, Pace Insights card, Manage Plan hub, Training
  Calendar (top-right icon), connected devices entry.
- Activities = workout history with filters (type/year/month) + manual "+"
  log; Performance section: weekly/yearly mileage trends, PRs, completed
  plans, achievements, all-time stats, Runna Score.
- Profile = shoes, units, audio cues, HR zones, subscriptions; Support = help.
- Trainer-bot fit: our 5 tabs (Today/Plan/Activity/Fitness/Settings) match.
  Borrow: weekly-mileage line on Today, and a Manage-Plan-style grouping.

## Today-tab daily card

- Planned session type (run/strength/rest), expert tips, weekly mileage at a glance.
- Entry points to Instant Workouts + Plan Adjustment tray.
- Fit: weekly-mileage-at-a-glance + one tip line are cheap adds to our Today card.

## Instant Workouts

- On-demand sessions (easy / long / intervals / tempo / race / parkrun) built
  from time, distance or pace goals.
- Logged to the Training Calendar but never alter the plan itself.
- Fit: "add an unscheduled run" flow that logs to history without touching the plan.

## Plan Realignment tray

- Pops up after ~3+ missed workouts or a missed week: options — skip missed,
  rearrange, extend the plan, rebuild to same end date, or continue unchanged.
- Longer gaps (>4 weeks) escalate: start new / restart.
- Fit: our plan-vs-actual matcher already flags missed; add a "get back on
  track" action card (regen options) on Plan/Today when misses accumulate.

## Training Calendar

- Drag-and-drop a workout within its week or to a neighbouring week
  (±1 week); schedule a start time; add Instant Workout per day.
- Deliberately restricted: no batch moves, no week swaps, no deleting planned
  runs — structure protected; permanent schedule changes live in Manage Plan.
- Fit: our per-day session chip row ≈ lighter version of this; if it grows,
  warn when a move affects progression (deload/taper/build weeks).

## Pace Insights (+ chart)

- After speed sessions, status one of: Pace on Point / Ahead of the Pack /
  Let's Review Your Pace / Variable Pace Detected.
- Chart: 5 most recent eligible speed workouts, reps normalised, fastest +
  slowest highlighted. Recommendations shift pace targets only after accept.
- Fit: our VDOT/pace hero could add an accept-or-ignore pacing re-baseline
  flow instead of silent recompute.

## Workout Insights & Briefings (AI)

- Post-run AI recap: plan-vs-actual, PB flags, motivation — unlocked by a
  thumbs rating on the run.
- Pre-run AI briefing (from day before): goal, weather, learnings from the
  previous similar workout, hydration/nutrition, plan context.
- Fit: we already show per-run AI review on Activity detail; add a pre-run
  briefing card to Today.

## Post-workout review loop

- Thumbs up/down + reason chips: "Paces too tough", "Workout felt too long",
  "Not feeling 100%" — fed back into coaching.
- Fit: cheap structured feedback on our done/partial/missed statuses.

## Runna Score

- Single progress number vs plan (built from estimated race times); shown with
  green shading, deliberately no universal scale.
- Fit: goal-pace delta trend we can surface on Fitness or Race.

## Personal Records & estimated race time

- PRs: elapsed-time based, outdoor runs only, milestone style; manual entry
  allowed. Editing a PR/race time recalibrates paces, may trigger plan update.
- Fit: our VDOT anchor already recalibrates on best effort; formalise a PR
  list and "recalibrate targets" action on Race page.

## Pace vs RPE units

- Global unit toggle: km/mi, °C/°F, and pace-target OR effort (RPE) targets.
  RPE mode used for heat/track/illness scenarios.
- Fit: effort-based sessions exist in trainer-bot; keep explicit "no pace
  analysis on RPE days" caveat (see training-hub notes).

## Manual log & link activity

- Manual "+" add (forgot GPS / GPS glitch / unsupported race).
- Plan → workout → Link Activity so a real run counts against the planned
  session; completed runs are not directly editable.
- Fit: link-activity reconciliation for our matcher (currently auto-matched
  by date + distance only).

## Adapt for Heat

- Day-before/day-of suggestion keyed to feels-like temp (roughly >68°F) and
  duration; colour-coded hourly forecast; recommends slower paces, swapping a
  long run to conversational, or "don't run outside".
- Fit: weather-aware adjustment of scheduled sessions (see training-hub for
  the pace math).

## Activity / Performance hub

- Filtered history (type/year/month), weekly + yearly mileage trends,
  achievements, completed plans, all-time stats.
- Fit: trainer-bot stats beyond single-activity detail (YTD volume, best
  week, plan completion rate).

## Source URLs

- https://support.runna.com/en/ (home / collection taxonomy)
- https://support.runna.com/en/collections/3431949-app-features-subscriptions-faqs
- https://support.runna.com/en/collections/3431932-training-hub
- https://support.runna.com/en/articles/10473504-your-quick-guide-to-navigating-the-runna-app
- https://support.runna.com/en/articles/10116460-how-to-use-instant-workouts
- https://support.runna.com/en/articles/10026375-how-to-use-the-plan-realignment-feature
- https://support.runna.com/en/articles/10137793-how-to-use-your-training-calendar
- https://support.runna.com/en/articles/14656203-what-are-pace-insights-and-how-do-they-work
- https://support.runna.com/en/articles/10751290-pace-insights-chart
- https://support.runna.com/en/articles/10494265-what-are-workout-insights
- https://support.runna.com/en/articles/13169751-what-are-workout-briefings
- https://support.runna.com/en/articles/7895279-what-is-my-runna-score
- https://support.runna.com/en/articles/7895208-how-do-personal-records-work-in-the-runna-app
- https://support.runna.com/en/articles/6206133-adjusting-your-training-units
- https://support.runna.com/en/articles/14666681-how-to-log-link-or-manually-add-an-activity
- https://support.runna.com/en/articles/15647483-how-does-runna-adapt-my-workouts-for-heat-and-humidity
- https://support.runna.com/en/articles/9973602-reviewing-your-workouts-to-support-your-training
- https://support.runna.com/en/articles/6206024-adjusting-your-running-schedule
- https://support.runna.com/en/articles/14666572-how-runna-calculates-your-mileage-and-how-to-adjust-it
- https://support.runna.com/en/articles/15231838-how-does-runna-build-your-training-plan-around-your-current-fitness
- https://support.runna.com/en/articles/15690947-understand-your-runna-workouts
