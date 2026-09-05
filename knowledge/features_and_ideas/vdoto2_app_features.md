# V.O2 (vdoto2) app — feature reference

Source: support.vdoto2.com "App Features" category + linked articles, crawled
2026-09. Research folder — NOT coach KB. Highest-fit source: V.O2 runs the same
VDOT-anchored model trainer-bot uses.

## VDOT Accuracy Scoring (planned vs actual GPS work)

- Analyzer auto-detects warm-up / intervals / recovery / cool-down from GPS and
  auto-logs reps ("Log Reps" fields).
- Overall accuracy % weighs pacing score over distance score. Easy-run splits
  scored individually — running faster than the VDOT range hurts more than
  slower. Higher-intensity work weighted more in mixed sessions.
- Manual split entry when no GPS device; analyzer ignores weather/course.
- Fit: blueprint for our plan-vs-actual matcher — per-rep comparison +
  composite accuracy score.

## Planned vs Completed

- Mark each scheduled workout complete / modified / incomplete (web + mobile);
  completed runs add to weekly mileage; completed-only totals feed consistency
  reporting.
- Fit: we map to our own done/partial/missed/extra model — same idea, keep.

## Stats — VDOT history

- Line chart of VDOT over time; Today tab notes how long you've trained at the
  current VDOT. If unchanged ~6 weeks, prompts a review of load/recovery/pace mix.
- Fit: VDOT-over-time chart reinforces "train at current, not goal, fitness".

## Stats — Your Paces (planned intensity mix)

- Planned volume per intensity (easy/threshold/interval/etc.) over 1W/1M/6M/1Y.
  Exposes whether emphasis matches the race goal (e.g. more threshold for
  half/marathon).
- Fit: "spend by zone" view answers "am I training the right paces?" — nice
  Fitness-tab add for us.

## Stats — Consistency + Training History

- Completed vs modified vs skipped over 1W/1M/6M/1Y (needs manual marking).
- Totals of runs, distance, cross-training over the same windows; elevation +
  avg HR when GPS synced.
- Fit: plan-adherence metric + training-load summary card on the calendar.

## Equivalent Performances

- Race result equated to physiological equivalents at other distances —
  presented as equivalents, not predictions.
- Different distances often give different VDOT; guidance: always use the
  highest VDOT for training intensities.
- Fit: our race-goal module can show "current fitness ⇒ equivalent times"
  honestly labelled (fitness page already does this table).

## Adjusting Training Paces (VDOT update loop)

- Update VDOT manually (tap score) or by entering an official race result.
- After a result the app offers to ACCEPT or REJECT the resulting pace change
  (reject if course/weather skewed it).
- Fit: race-result → new VDOT → regenerated paces with user veto is exactly
  the race-goal loop trainer-bot needs.

## Age-Graded VDOT Levels + Age Rank

- Age-graded levels 1–10 (white→gold) per age/gender, Dr. Daniels tables
  (levels don't apply 18–38). Age rank = your % within age group among
  community results; top-3 earns a medal.
- Fit: lets a solo runner judge PRs fairly as they age (community DB optional).

## Workout scheduling mechanics

- Move Workout: change a workout's date; do it before GPS data syncs if you
  swapped sessions. Reschedule ≠ modify ≠ skip — keeps matching honest.
- Repeating sets: nested sets, e.g. 4×[2×200 m R + 1×400 m R] — stops runners
  hammering short reps.
- Structured Strength Mode + custom cross-training types (e.g. Pool Running)
  with sets/reps/recovery scheduling.
- Fit: our calendar swap is Move Workout; set-within-set structure and
  non-run sessions are generator model upgrades.

## Sync & delivery

- Strava/Garmin/Coros import: first sync backfills ~30 days; poll thereafter.
- Watch delivery of planned workouts (Coros) for real-time guidance.
- Publish plan to personal calendar via Garmin `.ics` (Google/iCal/Outlook).
- Manual GPS file upload: `.fit` / `.tcx` / `.gpx`, batch over calendar or
  attach to one workout.
- Fit: `.ics` calendar export is a free dependency-light plan push; manual GPS
  upload is an escape hatch beyond Strava sync.

## Notifications

- Per-channel (push/email/in-app feed), feed-item delete/clear-all; reply to an
  email to post a comment.
- Fit: single-user nag preferences (missed-workout reminders, on/off).

## Race / PR profile page

- Upcoming + recent races on profile; add PRs historically; each result links
  to its calendar activity.
- Fit: race goal + PR list deserves its own view linked to the plan.

## VDOT calculator behaviors

- Enter by distance or by VDOT; adjusts for altitude and temperature
  (predicts effect, converts a result); dark mode.
- Fit: race-goal estimates can note course altitude/weather caveats.

## Share Workout card

- Shareable graphic from a photo or GPS route over the training summary.
- Fit: cheap progress-share card for a solo app.

## Source URLs

- https://support.vdoto2.com/category/new-app-features/ (index, pages 1–2)
- https://support.vdoto2.com/2024/02/vdot-accuracy-scoring/
- https://support.vdoto2.com/2022/11/new-feature-workout-accuracy/
- https://support.vdoto2.com/2022/10/latest-updates-to-v-o2/
- https://support.vdoto2.com/2022/08/new-feature-sync-workouts-to-coros/
- https://support.vdoto2.com/2022/07/new-feature-age-rank/
- https://support.vdoto2.com/2022/06/getting-to-know-your-pacing-needs/
- https://support.vdoto2.com/2022/06/tracking-your-vdot/
- https://support.vdoto2.com/2022/06/v-o2-stats-feature/
- https://support.vdoto2.com/2022/04/structure-strength-mode/
- https://support.vdoto2.com/2022/03/adjusting-your-training-paces-on-v-o2/
- https://support.vdoto2.com/2022/03/equivalent-performances/
- https://support.vdoto2.com/2022/02/repeating-sets-of-work/
- https://support.vdoto2.com/2022/02/show-todays-workouts/
- https://support.vdoto2.com/2022/01/new-app-feature-custom-activity-names/
- https://support.vdoto2.com/2021/11/new-feature-save-custom-paces-and-cross-training/
- https://support.vdoto2.com/2021/12/new-app-feature-custom-activity-names/
- https://support.vdoto2.com/2020/01/new-feature-move-workout/
- https://support.vdoto2.com/2020/04/view-vdot-paces/
- https://support.vdoto2.com/2020/05/updating-profile-page/
- https://support.vdoto2.com/2020/09/vdot-calculator-improved/
- https://support.vdoto2.com/2020/02/showing-your-vdot-workouts-in-separate-calendar-using-garmin-connect/
- https://support.vdoto2.com/2020/03/customizing-notifications/
- https://support.vdoto2.com/2019/08/age-graded-vdot-levels/
- https://support.vdoto2.com/2019/08/updated-vdot-paces-39-for-greater-accuracy/
- https://support.vdoto2.com/2018/05/specific-recovery-rest-options/
- https://support.vdoto2.com/2018/02/vdot-o2-now-compatible-strava/
- https://support.vdoto2.com/2024/02/auto-publish-vdot-training/
