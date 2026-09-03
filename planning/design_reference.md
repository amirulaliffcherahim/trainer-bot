# Design Reference — trainer-bot look & feel

Direction chosen (2026-09): **Runna-led shell + V.O2/VDOT data feel + Strava
accents**. Adidas Running not selected.

> Honesty flag: this describes the apps' known design languages from general
> knowledge — impression-level. Before visual implementation, verify against
> real screenshots (see Parked research: visual references).

## What each chosen app brings

### Runna — the shell (layout & motion)
- Mobile-first **plan-as-a-feed**: home screen = upcoming sessions stacked as
  big rounded cards, today's session first and biggest.
- Bold, saturated gradients and strong colour blocks; playful but athletic.
- Session cards carry: workout type, distance/duration, target pace bands,
  a short human "why", big tap targets.
- Streaks, rings, progress nudges — gamified but not childish.
- What we borrow: card-first home, today-hero, week strip, chunky CTAs.

### V.O2 / VDOT — the numbers (data presentation)
- Score-led calm: a single number (VDOT) as hero, then tidy pace tables
  (Easy/Marathon/Threshold/Interval/Repetition rows × per-mi/per-km columns).
- Dense but orderly tables; monospaced-ish numerals; minimal decoration.
- Equivalent-race table for goal setting.
- What we borrow: VDOT hero + pace-table language, mm:ss chips, equivalence
  view for "if I race X → what Y?"

### Strava — the accent (identity & activity)
- Sunrise orange as signature; clean whites/blacks around it.
- Activity timeline: date/time, type icon, distance/duration/pace stats row,
  kudos/comment counts (social — we skip the social, keep the pulse).
- What we borrow: activity summary rows (type icon + key stats), a restrained
  Strava-orange accent, light-first palette with strong contrast.

## Proposed trainer-bot visual identity (synthesis)
- **Base:** light-first, near-black text on white/off-white; optional dark
  mode later. Keep contrast high — mobile browsers outdoors.
- **Accent system:** one primary energetic colour for actions/session cards
  (candidate: electric blue-violet gradient — avoids looking like a Strava
  clone); Strava-orange reserved for anything about synced/activity data.
- **Type:** strong numerals for paces/times (tabular figures); friendly
  rounded sans for labels; short sentences, no filler.
- **Shape:** generous rounding on cards (Runna), 1–2 px hairlines inside
  tables (VDOT), flat icon set with activity colour coding (Strava).

## Screen map (v1 concept)
1. **Home — Today card.** One hero card: today's session (type, target,
   pace bands, why-now). Under it: tomorrow preview + "log how it felt"
   entry point when a workout is due to be rated.
2. **Calendar (the hub).** V.O2-style week/month plan calendar. Planned
   sessions on their day; matcher state rendered as status: done (tick /
   filled), partial (half), missed (strikethrough/dim), plus tiny "extra"
   dots for unmatched Strava runs. Tapping a day shows plan vs actual side
   by side.
3. **Plan view.** Week strip (tap days) over Runna-style session list;
   events pinned as banner cards (countdown).
4. **Fitness (VDOT) tab.** VDOT hero number + 1-trend sparkline, training
   pace table, equivalent-race table, latest PB source line.
5. **Journal/feedback.** Daily check-in flow (day feel → body map → note);
   "rate this workout" cards appear only for new/unrated activities.
6. **Settings/sync.** Strava connect, sync now, profile fields, knowledge
   sources shown (optional).

## Open styling questions (brainstorm later)
- Single accent vs per-session-type colours (easy=green, tempo=blue,
  interval=orange/purple — Runna uses type colours heavily)?
- Light-first vs dark-first; auto theme?
- How much of the old bot's "rojak" coach voice shows in copy vs clean UI?
- Charts: custom SVG sparklines vs a chart lib — no heavy dashboard needed
  for v1.

## File map
- design decisions land in planning/decisions.md when locked.
- Component/spec work belongs in a future implementation doc, not here.
