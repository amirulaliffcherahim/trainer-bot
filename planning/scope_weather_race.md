# Brainstorm — Scope / No-event plan / Weather & safety / Race-day

Session 2026-09. Candidates, not locked — numbers grounded in `knowledge/`
files (cited inline). Locked items move to decisions.md.

---

## 1. MVP slice (what ships first)

Proposal: four vertical slices, each independently useful.

- **S1 — Data + VDOT.** Strava OAuth connect (single user), initial backfill
  (paged, rate-limit aware), PB scan → VDOT → training paces + equivalent
  races. Fitness tab only. No plan yet.
- **S2 — Plan + Calendar.** Knowledge-rule plan generator (base mode + event
  mode), calendar hub, **matcher** (done / partial / missed / extra) run on
  every sync/webhook. This is the first "usable coach" week.
- **S3 — Feedback.** Rate new/unrated workouts, daily journal, v1 adjustment
  rules (missed workout → reschedule/trim; soreness → easy/mobility swap).
- **S4 — Race.** Event input → phased plan (see §4), taper, race-week/day
  cards, post-race reset + VDOT re-anchor.
- **S5 — Voice (parked).** Optional LLM explainer layer. NOT v1 — copy is
  hand-written templates from knowledge rules.

Questions to settle: does S1 need manual "this is a race/effort" tagging, or
is PB-scan fully automatic? Where does the plan's first generation happen —
immediately at S2 or after ≥2 weeks of Strava history?

## 2. No-event plan (base/maintenance mode)

What the plan contains when there is no upcoming event — candidate defaults:

- **Volume:** anchor to athlete's current ~4-week average from Strava.
  Progress ≤ **10%/week cap**; step-back week (60–70%) every 2–3 weeks
  (`volume_progression.md`).
- **Long run:** ≈25–30% of weekly volume, never >35%; grows ~1 km every other
  week.
- **Quality:** if volume is meaningful, keep 1 threshold/tempo session (T
  pace from VDOT); no-event mode is NOT junk-free-easy-only — one quality
  session holds fitness. If volume is low (<3 runs/wk), base first with
  easy-only.
- **Easy share:** 75–80% of weekly volume easy, conversational
  (`productive_training_week.md` / pacing KB).
- **Rest days:** full rest from running, active mobility instead — 20–30 min
  walks + 10-min head-to-toe routine (`rest_day_rules.md`). Wed/Sun bracket
  pattern generalizes to: rest the day after the long run + one mid-week.
- **Strength:** calisthenics KB 2×/wk optional on easy/rest-adjacent days.
- **Heat acclimatization:** base phase is the time to build 10–14 days of hot
  running (`heat_humidity.md`).

Open: does no-event mode still schedule interval (I-pace) work, or only
T + easy until an event exists? Preferred: T + easy only — I-work belongs to
event blocks.

## 3. Weather & safety smarts

- **Forecast source:** TBD — research flag: keyless options (open-meteo) vs
  paid; needs one fetch per planned session.
- **Plan-time adjustment** (`heat_humidity.md` rules): tropical heat 28–34 °C
  & 60–95% humidity → pace expectation drops **5–15 s/km**; suggest session
  before 07:00 / after 19:00, avoid 11:00–16:00; lightning within ~10 km →
  auto-cancel/reschedule indoor.
- **Fair matching:** matcher compares actual pace against the
  *weather-adjusted* target, not the nominal one — a hot slow run is not a
  miss and not a fitness regression.
- **VDOT guard:** PB scan must ignore/slow-count efforts run in extreme heat
  (else a heat-week looks like fitness loss).
- **Health safety:** physio red-flag rules stay above weather — any sharp
  pain/red flag stops sessions regardless (`physio/triage.md`).
- Terrain: hills/grade-adjusted pacing = separate research flag, not v1.

Open: humidity-only (wet bulb) thresholds, wind, AQI — in or out for v1?

## 4. Race-day product

- **Event input:** name, date, distance, type; optional target time — if
  absent, predict from current VDOT (equivalent table).
- **Phase windows (candidate, from runner + triathlon KBs):** 5K 8–10 wk,
  10K 10–12, HM 12–16 (longs top 16–18 km), Marathon 16–20+ (longs up to
  ~30 km territory), stepping up 10% rule with step-back weeks throughout.
- **Taper** (`volume_progression.md` + T100 KB): last 3 weeks — w−3 ≈75%,
  w−2 ≈55%, race week ≈35% easy-only; "10% underdone beats 1% overdone".
- **Race-week card:** countdown, last hard session cut-off, easy-only rule.
- **Race-day card:** goal pace bands from VDOT equivalents; negative-split
  plan (first half 5–10 s/km slower — pacing KB); pre-race fueling
  (1–3 h window; heavy sessions 200–300 g carb beforehand — nutrition KB);
  race hydration/electrolytes (>60 min → sodium).
- **Post-race:** race result becomes the freshest VDOT anchor automatically;
  recovery per rest-day rules + mobility flush routine; then prompt for next
  goal. Training-effort flag: "this wasn't a goal race" → exclude from anchor?

Open: A/B goals (goal + stretch); two events close together; mid-block event
reschedule; triathlon events (phase + weekly structure already in
`knowledge/triathlon/` — reuse later, not v1).

## Still open for the next round
- What happens on the step-back/recovery week when an event block is running?
- How far ahead can events be planned (max weeks)? cap?
- Do weather adjustments alter workout TYPE (interval→tempo in heat) or only
  pace expectation?
- S3 feedback fields — separate thread.
