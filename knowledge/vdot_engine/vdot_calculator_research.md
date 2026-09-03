# VDOT Calculator Engine — Research Findings (vdoto2.com)

> Reverse-engineered from the public client-side JS of vdoto2.com (Jack
> Daniels' official calculator, formerly Runsmart Project). Distilled for
> building our own Strava-driven training-plan app. All coefficients are
> verbatim from the shipped code (fetched 2026-09).

## What VDOT is
- VDOT = a performance score derived from a race/effort, NOT a lab VO2max.
- It is the implied VO2max of a runner with **average running economy** who
  could run that time: `VDOT = VO2-demand(speed) / fraction-of-VO2max-holdable(time)`.
- Two runners with equal VDOT can have different true VO2max (one fast-twitch
  economy, one high VO2max) — VDOT predicts *performance*, which is what
  training paces should key off.
- Inputs needed: distance (meters) + time (minutes) of one race/effort.
  Distance minimum is 800 m (below that, anaerobic share breaks the model).

## Inputs & outputs (vdoto2 calculator UI)
- Input: event distance (preset menu or custom) + time OR pace; also accepts
  distance derived from time+pace. Optional advanced: temperature (°C/°F) or
  altitude (m/ft), one at a time.
- Outputs: VDOT (1 decimal), training paces per type (Easy/Marathon/
  Threshold/Interval/Repetition/Fast Reps in /mi and /km + 1200/800/600/400/
  300/200 m columns), and Equivalent race times (Marathon→1500 m).
- Preset distances (meters): 42195, 21097.5, 15000, 10000, 5000,
  3218.688 (2 mi), 3200, 3000, 1609.344 (1 mi), 1600, 1500.
- VDOT validity range: 0 < VDOT ≤ 100.

## The math — VDOT from a race
1. **Speed.** Events ≥ 1200 m: `v = d/t` (m/min). Sub-1200 m gets a
   normalization toward the mile so short anaerobic races convert to an
   aerobic-equivalent speed (blend factor for 800–1200 m; fixed 2.1 factor
   for ≤ 800 m, 1600 m as reference).
2. **Oxygen demand** of that speed (aerobic-demand curve):
   `VO2 = 0.182258·v + 0.000104·v² − 4.6` (ml·kg⁻¹·min⁻¹, v in m/min).
3. **Sustainable fraction** for duration t (minutes):
   `f(t) = 0.8 + 0.298956·e^(−0.193261·t) + 0.189439·e^(−0.012778·t)`.
4. **VDOT = VO2 / f(t)**.

Worked: 5K in 20:00 → v = 250 m/min → VO2 = 47.46 → f(20) = 0.953 →
**VDOT ≈ 49.8** (matches engine output).

## Race-time prediction (the Equivalent tab)
- Inverse of the demand curve gives velocity from an effort level x:
  `velocity(x) = 29.54 + 5.000663·x − 0.007546·x²` (m/min), x = VDOT·f(t).
- Solve for the time t where `distance = t · velocity(VDOT·f(t))` — the engine
  runs 3 Newton iterations, initial guess `t = d/(4·VDOT)`.
- Equivalent race = the time each distance returns for the SAME VDOT (input
  row echoes the exact entered time). No terrain/weather baked in.

## Training paces from VDOT
Pace for multiplier m at unit distance u: `u / velocity(VDOT·m)`.
- **Easy:** m = 0.62 (slow bound) to 0.70 (fast bound).
- **Threshold:** m = 0.88.  **Interval:** m = 0.975.
- **Repetition:** Interval pace minus 6 s per 400 m.
- **Fast Reps** (200–600 m): Rep pace minus 4 s per 200 m.
- **Marathon pace:** separate Newton solve at 42 195 m (~82% of VDOT at
  VDOT 50, i.e. the model's marathon fraction, not a fixed multiplier).
- UI band labels (Easy "59–74% VO2max", Threshold "83–88%", Interval
  "97–100%") are descriptive marketing text; the shipped multipliers above
  are what the engine actually uses.

## Beginner (slow-VDOT) adjustment
- VDOT < 39 uses a substituted score `SRVDOT = VDOT·(2/3) + 13` for Easy,
  Interval and Rep paces (so novices get achievable paces).
- Threshold instead uses the average `(SRVDOT + VDOT)/2`. Marathon pace is
  NOT substituted.

## Temperature & altitude adjustments
Both rescale time, then recompute a slower/faster VDOT pair ("actual vs
anticipated" toggle):
- Heat: +0.16667% per °C above 15 °C. 25 °C ⇒ ≈ +2.8% time
  (marathon ≈ +5 min).
- Altitude: +(0.004·m − 3)% (negative below 750 m, so ≈ neutral at sea
  level). 1000 m ⇒ +1%, 3000 m ⇒ +9%.

## Validation (replica vs engine)
Re-implementing the functions above reproduces engine outputs exactly:
- 5K 20:00 → VDOT 49.8 → mile 5:51, 10K 41:29, HM 1:31:53, M 3:11:23.
- VDOT 50 → 5K 19:56, M 3:10:46; VDOT 45 → 5K 21:49, M 3:28:23
  (matches Daniels' published tables).

## Reference implementation (Python)
```python
import math

def vo2_demand(v):            # v in m/min -> ml/kg/min
    return 0.182258 * v + 0.000104 * v * v - 4.6

def frac(t):
    return (0.8 + 0.298956 * math.exp(-0.193261 * t)
            + 0.189439 * math.exp(-0.012778 * t))

def speed_param(d, t):        # normalize sub-1200 m races toward 1600 m
    if d >= 1200:
        return d / t
    if d > 800:
        i, r = 1600 / d, (1600 - d) / 800
        return 1600 / (t * (i + 0.1 * r))
    return 1600 / (t * (800 / d) * 2.1)

def vdot(d, t):               # d meters, t minutes
    return vo2_demand(speed_param(d, t)) / frac(t)

def velocity(x):              # inverse demand curve, m/min
    return 29.54 + 5.000663 * x - 0.007546 * x * x

def predicted_time(v, d):     # Newton x3, from engine
    i = d / (4 * v)
    for _ in range(3):
        e = math.exp(-0.193261 * i)
        r = 0.298956 * e + math.exp(-0.012778 * i) * 0.189439 + 0.8
        o = (v * r) ** 2 * -0.0075 + v * r * 5.000663 + 29.54
        c = 0.298956 * e * 0.19326
        s = c - math.exp(-0.012778 * i) * 0.189439 * -0.012778
        l = r * s * v * -0.007546 * 3
        a = s * v * 5.000663 + l
        i -= (i - d / o) / (d * a / (o * o) + 1)
    h = d / i
    u = d / h                  # predicted minutes
    if d >= 1200:
        return u
    return u / (h / speed_param(d, u))
```

## Implications for our Strava-driven trainer app (our notes)
- VDOT needs ONE race/effort (distance + time ≥ 800 m). Strava gives us the
  raw material: recent PBs, best-efforts, or a chosen recent race activity;
  worst case a fresh "time-trial" workout prompt.
- Feedbacks/adjustment: new race or effort ⇒ recompute VDOT ⇒ regenerate every
  pace band + plan. Recompute-from-history lets us show VDOT trend over weeks
  (rolling best effort) — engine math above is cheap and deterministic.
- Plan generation = paces at fixed % of VDOT + Runna-style workout templates;
  the "AI talks, code does math" principle from our old bot still applies.
- Licensing: the *method* is Jack Daniels' published Running Formula
  equations; reimplementing them is standard practice. Do not copy vdoto2's
  code or tables wholesale — write our own against the formulas.

## Sources
- vdoto2.com/calculator + /calculator/embed (UI, inputs, result tabs)
- /bundles/js/frontend.js (controller flow: distance/time/pace → VDOT → tabs)
- /bundles/js/global.js (Formula object — all math above)
- fellrnr.com/wiki/VDOT (concept: implied VO2max, avg running economy)
- Origin method: Jack Daniels, "Daniels' Running Formula"
