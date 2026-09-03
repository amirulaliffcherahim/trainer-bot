# Knowledge Base Index

Curated markdown corpora for the trainer bot. Each subfolder is a retrieval
namespace — `ingest_kb.py` reads `knowledge/<folder>/*` and chunks every file
by heading into `kb_chunks`, keyed by folder name.

## Wiring status

| Folder | Persona | Retrievable by bot? |
|---|---|---|
| `runner/` | runner | ✅ wired (`PERSONA_KEYS`) |
| `calisthenics/` | calisthenics | ✅ wired |
| `mobility/` | mobility | ✅ wired |
| `physio/` | physio | ✅ wired |
| `triathlon/` | — | ⛔ scaffold only — no persona yet |
| `nutrition/` | — | ⛔ scaffold only — no persona yet |
| `vdot_engine/` | — | 🛠 product research (not coach KB) — no persona |

`vdot_engine/` holds engineering research for building our own Strava-driven
plan app (vdoto2.com calculator math, decoded) — technical reference, not
coaching retrieval content. Ingesting it into the RAG would pollute coach
answers; keep it out of the bot KB. Ignore it if you ever re-wire personas.

`triathlon/` and `nutrition/` were added as a content scaffold (2026). They
will be ingested if a matching persona key exists, but no current bot persona
queries them. To activate: add `personas/triathlon.md` + `personas/nutrition.md`
and extend `PERSONA_KEYS` in `personas.py` — then every user message costs 6
persona passes instead of 4 (plan for the token cost).

## Ingestion note

The bot auto-seeds the KB only when `kb_chunks` is empty. New/changed files
under an existing folder require a manual re-ingest:

```bash
python ingest_kb.py --db trainer_data.db
# or --tf for the deterministic test embedder
```

## Verified sources (fetched 2026-09)

- **runner/productive_training_week.md** — Strava Stories, Coach Nick Bester,
  "A Productive Weekly Training Program for Runners" (Aug 2024)
  <https://stories.strava.com/articles/a-productive-weekly-training-program-for-runners>
- **triathlon/\*** — T100 Triathlon, "How to Train for Triathlons: Everything
  You Need to Know"
  <https://t100triathlon.com/articles/training/how-to-train-for-triathlons/>
- **nutrition/\*** — IRONMAN, "Eat Like An IRONMAN: 6 Nutrition Rules For
  Endurance Athletes"
  <https://www.ironman.com/training/nutrition/daily-nutrition/eat-ironman-6-nutrition-rules-endurance-athletes>
- **mobility/post_workout_stretching.md** — Mayo Clinic, "Stretching: Focus on
  flexibility" (Nov 2023). **Substitute**: the user-supplied Technogym article
  <https://www.technogym.com/en-MY/stories/post-workout-stretching/> is
  CloudFront-blocked (HTTP 403 site-wide); Mayo Clinic guidance covers the same
  post-workout stretching topic from a medical source.

## Candidate future sources (verified to exist, not yet distilled)

URL guessing failed without a search API key (run `/web-tools` in pi) and some
sites (Technogym, Harvard Health) block fetches. These IRONMAN tag pages list
articles whose content is not yet captured:

- IRONMAN Nutrition hub: <https://www.ironman.com/training/nutrition> — e.g.
  "Endurance Nutrition Basics 101: How to Fuel For an IRONMAN 70.3", "Race
  Nutrition Made Easy", "How much should you be drinking when you're sweating?"
- IRONMAN Swim hub: <https://www.ironman.com/training/swim> — e.g. "How to
  Improve Swimming Technique With 6 Simple Fixes", "Swimming Workouts: 4
  Structured Sets To Build Endurance", "5 Causes of Open Water Swim Anxiety"

## Content rules (kept consistent with repo convention)

- Markdown only; chunked by `#`/`##`/`###` heading.
- Sections stay under ~1400 chars so chunking never hard-splits mid-thought.
- Bullet style, terse, action-oriented. Numbers preserved exactly from source.
- No invented guidance: retrieval shows no-match → say "no data".
