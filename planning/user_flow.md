# How the AI Works — Your Daily Experience

What actually happens when you use the bot, step by step, with example dialogues.
(Under-the-hood detail is in `plan_v2.md` — this doc is the user journey.)

---

## 0. The pipeline in one picture

```
you ──> guardrails (code, safety first)
   ──> understanding (AI: text → structured data, validated)
   ──> the numbers (code: your real stats, computed)
   ──> 4 experts think (AI: runner / calisthenics / mobility / physio, in parallel)
   ──> one answer (AI: editor merges, physio wins conflicts)
   ──> checks (code: citations, no invented numbers)
   ──> buttons (one-tap actions under the reply)
```

Everything below is this pipeline wearing different clothes.

---

## 1. First contact — `/start`

```
Bot:  Welcome, Amirul! I'm your trainer — four experts in one.
      Runner coach · Calisthenics coach · Mobility coach · Physio
      You're in BASE phase (easy miles until ~Jul 2026).
      [Today's plan]  [What's base phase?]  [Log my weight]
```

- Bot asks a few setup questions: current weight, any niggles, confirm race dates
- One answer stores your profile; nothing is guessed
- Goal: get you logging within 2 minutes, not 20

## 2. Daily logging — text message

**You:** `Tuesday easy run done, 5km, felt good, RPE 6`

**Under the hood:**
1. Guardrails — no red flags in your text ✓
2. DeepSeek extracts: `{session_type: easy_run, distance_km: 5, rpe: 6, completed: true}` → validated
3. Code computes: 7-day fatigue trend, this week's volume vs last week
4. Four experts draft in parallel
5. Editor merges into one reply, checks it

**Bot:**
```
Nice easy 5k ✅  Volume this week is +8% vs last — right on the ≤10% rule.

Tomorrow is legs day — keep it light since Thursday is an easy run.
Don't skip the quad stretch: 2×45s each side after the session.
[SOURCE: mobility/cool-down]  [SOURCE: calisthenics/legs]

[Log weight]  [Tomorrow's plan]
```

That's it — one message, all four perspectives, no typing of commands.

## 3. Pasting a photo — Strava screenshot

**You:** *(sends screenshot)* `Saturday long run done`

**Under the hood — the careful part:**
1. **Read pass:** local OCR reads the text in the image → DeepSeek turns it into raw fields `{distance_km, moving_time_min, avg_pace, avg_hr, elevation_m, date}`
2. **Math check (code):** computes pace = time ÷ distance. If the parsed "pace" disagrees with the math by >5 s/km → flagged **UNCERTAIN**
3. **Plausibility (code):** distance 0.1–50 km? HR 30–220? date recent?
4. **Plan comparison (code):** vs what Saturday's plan prescribed

**Bot:**
```
Read: 10.42 km · 72:38 · 6:58/km
Planned: 10 km easy @ 7:10

→ You beat target pace by 12 s/km. Correct?
[Correct]  [Fix: distance]  [Fix: pace]  [Fix: date]
```

- You tap once. **Only confirmed numbers enter your history and stats.**
- If the math check caught an inconsistency, the bot says so instead: *"The pace shown (6:10) doesn't match distance/time (6:58) — which is right?"*
- If reading fails twice: *"No problem — type distance and time."* No guessing, ever.

## 4. Asking for advice

**You:** `Quad feels tight, long run tomorrow — what should I do?`

**Under the hood:**
- Guardrails ✓ (not a red flag — but physio gets priority weight)
- Facts: last 3 runs, fatigue trend, tomorrow's prescription

**Bot:**
```
Physio first: no red flags — tightness, not sharp pain. OK to run, but:
  • warm up 10 min slow + 4×30s walk brisk before starting
  • keep tomorrow at easy pace; skip if it sharpens during the run
  • 2×45s quad stretch + foam roll tonight

Runner coach: tomorrow stays as planned (10 km easy), no pace pressure.
Mobility: activation set before you head out → [Routine]
Calisthenics: fine to keep Friday core; skip Thursday legs if still tight.

[Physio quick check]  [Mobility routine]
```

One answer, safety first, and the conflict rule in action: if physio had said *rest*, the runner coach's long run would have been overruled *and the bot would say so*.

## 5. What you never have to do

- Never type commands — every action is a button
- Never re-explain your history — the bot computed it
- Never trust a number you can't verify — screenshots are echoed back
- Never guess your plan — `/today` knows the phase, the date, and the rules

## 6. What the bot does on its own (proactive)

| When | It sends |
|---|---|
| Sunday | Weekly recap: km, fatigue trend, next week's preview + **challenge proposal** → [Accept] [Skip] |
| Fatigue trend up 2+ weeks | Swap today's run for rest → [Swap] [Log rest] |
| Same symptom twice in 14 days | Physio check → [Quick check] |
| 2+ missed sessions in 10 days | Gentle replan offer → [Replan] (never guilt) |
| Phase change in 7 days | "Taper starts next week" → [Show plan] |
| No logs 3+ days | Soft nudge with streak context → [Quick log] |
| ≥6 quality runs + pace shift | Prediction update: *"Your recent runs suggest 2:5X is realistic — [See prediction] [Update target]"* |

Hard limits: max 2 pushes/day, quiet hours 22:00–07:00, nothing during taper except race prep, dismiss a type → it won't recur for a week. `/mute` for a day or a week.

## 7. The prediction (when it happens)

**You tap** `[See prediction]`:

```
Prediction (from your best verified effort: 10.42 km @ 6:58):
  Half marathon: 2:44 – 2:53  (±5% band, Riegel formula, code-computed)

Caveats: assumes consistent training, KL heat adds time, course profile unknown.
Current target: sub-3:00 — you're ahead of it.
[Update target to 2:50]  [Keep 3:00]  [How is this calculated?]
```

- The math is deterministic code (Riegel formula), the AI only explains it
- The target never changes without your tap

## 8. Weekly rhythm (what a typical week looks like)

```
Mon  strength (upper) — you log it                    → brief form advice
Tue  easy/tempo run — you log it                      → pace check vs plan
Wed  rest — bot silent (unless fatigue trend says otherwise)
Thu  easy run + legs — you log + photo                → echo-confirm + advice
Fri  core — you log                                   → mobility nudge if tight
Sat  long run — photo                                 → echo-confirm, volume math
Sun  rest — bot pushes: recap + challenge + next week
```

Total: ~5 minutes of your day. Every interaction makes the next answer more accurate.
