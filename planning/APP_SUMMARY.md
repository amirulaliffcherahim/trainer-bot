# trainer·bot — App Summary (2026-09)

Single-user running coach, mobile-browser-first. Strava API data → live VDOT
anchor → personalized plan → match reality → feedback/journal → adjust →
race prep. Design law throughout: **the AI talks, the code does the math.**

## UI (SvelteKit, hand CSS, 5 tabs)
- **Today** — daily check-in (energy/sleep/soreness/note), coach note from
  the adjustment engine, today's session card with ✓/~ /✗ match status,
  sync button.
- **Plan** — build/renew wizard: pick training days, then each day's type
  (Auto / Easy / Tempo / Speed / Long), add goal race (category + date + km).
  14-day calendar list; every row has inline Easy/Tempo/Speed/Long swap
  chips; status tags + KB reason under each session; rest days dim.
- **Activity** — recent runs; tap to open a deterministic AI review (zone
  classification vs VDOT) + feedback: felt / RPE 1–10 / soreness / note;
  "needs feedback" badge per unrated run.
- **Fitness** — VDOT hero, source line, training-pace table per mile/km,
  equivalent race times.
- **Settings** — Strava connect / reconnect (scope-aware), sync now,
  disconnect; friendly states for missing creds or insufficient scope.

## Backend (adapter-node, single process)
- `hooks.server.ts` starts the **hourly auto-sync** on first request.
- APIs: status, auth (oauth/strava|callback|disconnect), sync, fitness,
  plan (GET/generate/prefs/session-swap), events CRUD (one active event),
  activities + feedback, journal GET/PUT, race briefing.
- Storage: SQLite (`node:sqlite`) at a data path separate from source —
  migrations v1..v5 (token, activities, vdot snapshots, events + plan +
  feedback + prefs.kinds, journal).

## Engine (pure & deterministic, KB-cited)
- **sync.ts** — paged Strava backfill (year window), upsert by id,
  rate-limit aware; **scheduler** runs it hourly.
- **fitness.ts** — PB scan on **5 km and longer only** (±15% buckets up to
  marathon; manual/trainer/commute excluded; 120-day window) → best VDOT
  snapshot.
- **vdot.ts** — full VDOT engine port: demand curve, %-holdable fraction,
  3×Newton race-time prediction, pace multipliers (.62–.70 E / .88 T /
  .975 I, rep/fast-rep offsets), slow-VDOT substitution.
- **plan.ts** — weekly targets from a 28-day volume anchor (floor 18 km),
  ≤10%/wk growth, step-back every 3rd week, event phases (build →
  taper 75/55/35 → race week easy-only → post 60%), per-day kinds honored
  (speedwork allowed anytime the user picks it, softened in taper).
- **match.ts** — athlete-local-date matcher: done ≥90% / partial 50–90% /
  missed / rest-flag & second-run extras.
- **review.ts** — pace zone classifier with template copy (easy/threshold/
  interval/above/slow; honest "no anchor" states).
- **s3.ts** — adjustment rules (sharp → rest; noticeable → easy 60%;
  energy ≤2 → easy 70%; felt-hard → back off tomorrow; missed → no chase;
  <6h sleep → easy 80%).
- **race.ts** — race briefing: goal from target or VDOT prediction,
  negative-split plan, taper table, fuel/hydration, post-race checklist.

## Calculation walk-through
1. Sync: distances/times stored raw (m, s), grouped by athlete-local date.
2. Anchor: best 5K+ effort → VDOT = demand(speed) ÷ f(time) → paces s/km.
3. Plan: target km/week → day shares (long 30%, hard ~8% ea, easy rest) →
   distance + VDOT pace per session; adjustment overlay on today/tomorrow.
4. Match: today's activity vs plan distance → status; feedback/journal
   enrich the next generation.

## UX principles
- One-thumb mobile: cards + chips + bottom tabs, no modals needed.
- Honest states everywhere: no VDOT → "no anchor", no scope → reconnect
  path, no match → miss, not assume.
- Every plan row explains itself (KB citation) so the coach is transparent.
- Feedback loops are lightweight and only ever ask about new/unrated data.
