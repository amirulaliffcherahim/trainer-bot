# Gemini FULL PLAN EXPORT — raw reference (unmodified)

Source: user's Gemini conversation export. Training content is authoritative
and has been merged into `plan_v2.md` and the knowledge corpora. Tech/coding
sections (§5 architecture, §8, §12 pm2/Cloudflare items) are SUPERSEDED by
later decisions (DeepSeek V4-Flash, local OCR, local embeddings, 4-persona
committee) and are intentionally NOT merged.

---

# FULL PLAN EXPORT (verbatim)

## 1. Project Overview

We are building an AI Personal Trainer Telegram Bot and an accompanying
14-week-plus training system designed to coach an underweight runner from
baseline endurance to successfully completing the SELMAR Half Marathon and
TwinCity Half Marathon without injury. The bot acts as a multimodal, daily
interactive coach—digesting text logs (stress, weather, soreness, RPE) and
images (Strava/Garmin watch stats, meals, form photos), storing structured
data in SQLite, and providing dynamic workout adaptations based on a rolling
context engine.

## 2. Athlete Profile

- Height: 175 cm
- Weight: 55 kg
- Body Status: Underweight (Targeting caloric surplus: ~2,700 kcal daily /
  ~99g–110g protein daily, nominal target ~100g protein).
- Current Running Baselines: 5K in 35:00, 10K in 1:10:00 (~7:00 min/km pace).
- Primary Target: SELMAR Half Marathon (Sub-3 Hour goal / Target Pace
  ~7:06 – 7:10 min/km). [NOTE: the export's own numbers conflict — 7:06/km =
  2:29:47 finish; primary finish target below is authoritative]
- Primary Finish Time Target: 2 hours 30 minutes (2:29:47 at 7:06 min/km pace).
- Secondary / Safe Backup Target: 2 hours 45 minutes (2:45:00 at 7:49 min/km pace).
- Location & Climate Context: Kuala Lumpur / Selangor, Malaysia (High heat and humidity).

## 3. Race Calendar & Training Phases

### Race 1: SELMAR Half Marathon (November 1, 2026)

Goal: Sub-3 Hours (< 3:00:00) [see note above — use 2:30:00]. 14-Week
Progression Overview:

- Week 1 (Jul 27 – Aug 2, 2026): 17 km total (4 km easy + 5 km easy + 8 km long run).
- Week 2 (Aug 3 – Aug 9, 2026): 19 km total (4 km easy + 5 km easy + 10 km long run).
- Week 3: 23 km total (5 km easy + 6 km easy + 12 km long run).
- Week 4 (De-load): 15 km total (3 km easy + 4 km easy + 8 km long run).
- Week 5: 25 km total (5 km easy + 6 km tempo + 14 km long run).
- Week 6: 28 km total (6 km easy + 6 km tempo + 16 km long run).
- Week 7: 31 km total (6 km easy + 7 km interval [1 km warm-up + 4x800m @
  target pace with 2 min jog rest + 1 km cool-down] + 18 km long run).
- Week 8 (Trial 1 / De-load): 30.1 km total (4 km easy + 5 km easy +
  21.1 km slow low-stress trial run @ 8:00/km).
- Week 9: 31 km total (6 km easy + 7 km tempo + 18 km long run).
- Week 10 (Trial 2): 31.1 km total (5 km easy + 5 km easy + 21.1 km race-pace
  rehearsal @ 7:10/km).
- Week 11 (Taper 1): 23 km total (5 km easy + 6 km easy with 4x100m strides +
  12 km long run).
- Week 12 (Taper 2): 16 km total (4 km easy + 4 km easy + 8 km long run).
- Week 13 (Taper 3): 13 km total (4 km easy + 4 km easy with 4x100m strides +
  5 km shakeout).
- Week 14 (Race Week): 26.1 km total (3 km shakeout + 2 km shakeout +
  21.1 km SELMAR Race Day).

### Race 2: TwinCity Half Marathon (January 24, 2027)

Goal: Sub-2:30 or Sub-2:25 target refinement (~6:50 – 7:00 min/km pace).
12-Week Post-SELMAR Extension:

- Weeks 1–2 Post-SELMAR (Nov 2 – Nov 15, 2026): Active Recovery & Reverse
  Taper (Nov 7: 3 km shakeout; Nov 10: 4 km easy; Nov 12: 5 km easy;
  Nov 14: 8 km easy @ 8:00/km).
- Weeks 3–4 (Nov 16 – Nov 29, 2026): Base Re-Building (Nov 17: 5 km;
  Nov 19: 6 km; Nov 21: 10 km @ 7:45/km; Nov 24: 5 km with 3 km tempo @
  6:45/km; Nov 26: 6 km; Nov 28: 12 km).
- Weeks 5–8 (Nov 30 – Dec 27, 2026): Build & Threshold (Dec 1: 6 km with
  4 km tempo @ 6:40/km; Dec 5: 14 km; Dec 8: 4 km; Dec 10: 5 km; Dec 12:
  10 km; Dec 15: 6 km with 4x800m @ 6:30/km; Dec 19: 16 km with last 3 km
  @ 7:00/km; Dec 22: 6 km tempo; Dec 26: 18 km).
- Weeks 9–10 (Dec 28, 2026 – Jan 10, 2027): Peak & Simulation (Jan 2:
  TwinCity Trial Run 21.1 km @ ~7:00/km; Jan 5: 5 km with strides; Jan 7:
  6 km; Jan 9: 12 km).
- Weeks 11–12 (Jan 11 – Jan 24, 2027): Taper & Race Week (Jan 12: 4 km;
  Jan 14: 4 km; Jan 16: 7 km shakeout; Jan 19: 3 km shakeout + strides;
  Jan 23: 2 km shakeout; Jan 24: TwinCity Race Day 21.1 km).

## 4. Weekly Training Schedule

### 3-Day Running Split + 3-Day Strength Schedule

- Monday: Rest / Dynamic Stretch + Upper Body Strength
- Tuesday: Easy Run / Tempo Run / Speed Work (~7:45 – 8:15 min/km easy,
  6:40 – 6:45 min/km tempo, 6:30 min/km intervals) + Upper Body / Light
  Upper Body
- Wednesday: Full Rest Day (Non-negotiable)
- Thursday: Easy Run + Leg Day Strength
- Friday: Core Workout + Mobility (Optional 5-min form drills: High Knees,
  Butt Kicks, A-Skips, 2x50m Strides)
- Saturday: Progressive Long Run (Easy pace ~8:00/km baseline, peak segments
  @ 7:05 – 7:10 min/km)
- Sunday: Full Rest Day / Active Mobility (Non-negotiable)

### Selected Strength Exercises

- Upper Body: Military Push Up, Chair Dip, Australian Pull Up, Diamond Push
  Up, Pike Hold.
- Lower Body: Squat, Bulgarian Split Squat, Calf Raise, Tibial Raise (for
  shin splint prevention), Side to Side Squat.
- Core: Plank, Side Plank, Mountain Climber, Leg Raises, Glute Bridges.

### Daily 10-Minute Head-to-Toe Mobility Routine

1. Neck Circles: 5x each direction.
2. Standing T-Spine Rotations: 8x each side.
3. Cat-Cow Stretch: 8x slow cycles.
4. World's Greatest Stretch: 5x each side.
5. Kneeling Hip Flexor Stretch: 30s each side.
6. 90/90 Hip Switches: 8x smooth switches side-to-side.
7. Deep Squat Hold & Ankle Shift: 60s.
8. Ankle Circles & Toe Spreads: 10x each foot.
9. Calf & Shin Stretch: 30s each leg.

## 5. Bot Features & Commands

[SUPERSEDED — see plan_v2.md. Export had: python-telegram-bot v20+, google-genai
SDK, SQLite, .env with GEMINI_API_KEY, commands /start /today /summary /log
/help, Gemini 1.5 Flash vision, rolling 5-7 day context, ALLOWED_USER_IDS
middleware.]

## 6. Personas / Experts

[SUPERSEDED — single "Expert AI Personal Running & Strength Coach" persona.
Later decision: 4-persona committee (runner/calisthenics/mobility/physio).
Its rules are preserved in plan_v2.md design laws: prioritize tendon/bone
safety over volume; mandatory rest Wed/Sun; auto-scale-down on high stress,
>33°C heat, or joint/tendon pain.]

## 7. Knowledge Content

### Recovery & Yoko Yoko Application

- Best Usage: Apply 30–60 minutes before sleep after showering for
  DOMS/muscle soreness (calves, quads, hamstrings, glutes).
- Contraindications: Do NOT apply right before sweating/heat, on fresh sharp
  joint pain/acute tendonitis, under tight compression garments, or
  immediately after a hot shower.

### Muscle Soreness (DOMS) vs. Injury

- DOMS: Symmetrical, dull aching muscle tightness; fades after warming up.
- Injury Warning: Unilateral, pinpoint sharp pain or bone tenderness;
  worsens during activity or walking down stairs.

### Quadriceps Tendon Strain Protocol

- Ice 15 mins 2–3x/day, foam roll upper/middle quads (never directly on the
  painful tendon spot above the kneecap), skip knee-loading exercises, and
  take extra rest if stairs provoke pain.

### Rest Day Recovery Rules

- Engage in active mobility and 20–30 min walks.
- Maintain protein intake (20–30g every 3–4 hours, totaling ~99g–110g daily).
- Sleep 7.5 to 9 hours per night.
- Do NOT run recovery runs on rest days (running impact is 2.5x–3x body weight).

### SELMAR Race Day Pacing Strategy (Target: 2:30:00)

- KM 1 – 3: Controlled Warm-up (~7:20/km) → Cumulative ~00:22:00
- KM 4 – 10: Target Rhythm (~7:05/km) → Cumulative ~01:11:35
- KM 11 – 16: Cruising Efficiency (~7:05/km) → Cumulative ~01:54:05
- KM 17 – 21.1: Finish Push (~7:00/km) → Cumulative 02:29:47

## 8. Tech Decisions

[SUPERSEDED — Gemini 1.5 Flash, google-genai, hosting options, pm2/Vite,
Cloudflare Tunnel all replaced or out of scope. See plan_v2.md §4.7 (DeepSeek)
and §10 (Deployment).]

## 9. Evaluation & Acceptance Criteria

1. Daily Log Verification: "Work stress 8/10, hot weather 33C, tight right
   quad" → bot acknowledges history, adjusts day's load, logs in SQLite.
2. Vision Processing Verification: Strava screenshot + "Saturday long run
   done" → extract distance/pace, evaluate vs ~7:10/km target, recovery
   feedback, store path.
3. Memory Persistence Test: "How has my fatigue been looking over the past
   3 days?" → accurate summary from SQLite.

[These match plan_v2.md §12 acceptance items 1–3.]

## 10. Risks & Things to Watch

- Volatile Mileage Spikes: Unstructured jumps (0→12 km or 4→16 km) trigger
  overuse injuries.
- Quadriceps Tendonitis: High eccentric load from Bulgarian split squats
  paired with running volume risks tendon inflammation above the kneecap.
- Tendon/Bone Lag: Tendons require 3 to 6 months to adapt to impact forces,
  trailing behind cardiovascular gains.
- Chemical Burns: Counterirritants (Yoko Yoko) under tight compression or
  right before sweating cause skin irritation.
- [Port/Docker binding items — portfolio site, out of scope]

## 11. OPEN QUESTIONS

- Exact hosting provider for the Telegram Bot (Docker on local server vs
  Render vs Railway vs Replit). [plan_v2.md §10: VPS or home machine +
  systemd/Docker]
- Swapping a September Tempo run for an additional 800m interval workout in
  Week 5 or Week 6 based on leg adaptation.

## 12. REJECTED ALTERNATIVES

- Monday 5x800m Race Pace Repeats: rejected — hard repeat sprints after
  Saturday long runs create excessive impact on 55 kg body weight.
- Daily Recovery Runs / 5–6 day running split: rejected — removes joint
  repair windows and rest days.
- [pm2/Cloudflare items — portfolio site, out of scope]

## 13. Anything Else

- PLAN.md specification was created as a markdown execution blueprint for CLI
  AI coding agents. [This is first_plan.md's origin; superseded by plan_v2.md]
