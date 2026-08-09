# The Trainer Bot — Explained Simply

A plain-language walkthrough of what we're building and why the plan looks the way it does.

---

## 1. What is it?

A **personal trainer that lives in Telegram**. You message it (text or photos), it replies with coaching advice — what to run today, how hard, whether to rest, how to strengthen, how to stretch, and whether something hurts in a worrying way. It **remembers** everything you tell it.

Two races matter: **SELMAR Half Marathon (Nov 2026)** and **TwinCity Half Marathon (Jan 2027)**. The bot trains you toward them.

## 2. Why is this hard?

The AI (DeepSeek — the cheap, fast model doing most of the thinking) is a brilliant talker but a **bad accountant**. If you ask it to calculate your average pace over the week, it might say 6:52 when the real number is 7:03. It doesn't make mistakes on purpose — it just isn't built for math. It also **forgets** things and **invents** answers when it doesn't know.

So the whole design has one rule:

> **The AI does the talking. The code does the math.**

## 3. The team of four experts

The bot isn't one voice — it's **four experts in a room**, and one editor who writes the final reply:

| Expert | Knows about |
|---|---|
| **Runner coach** | Half-marathon training, pacing, weekly volume, race phases |
| **Calisthenics coach** | Bodyweight strength: push-ups, pull-ups, squats, core |
| **Mobility coach** | Stretching, joint mobility, warm-ups, fixing tightness |
| **Physio** | Injuries: what's risky, what to rest, rehab steps, red flags |

When you send a message, **all four think about it separately**, then the editor merges their drafts into **one answer** — so a single reply covers running, strength, mobility, and injury safety at once.

There's a rule for disagreements: **the physio wins**. If the runner coach wants you to run 12 km tomorrow but the physio says your quad needs rest, the answer tells you to rest — and says why openly. Safety is never overruled by training ambition.

Four voices cost more time than one. That's deliberate — see section 6.

## 4. What happens when you send a message?

1. **Safety check** (code, not AI). "Chest pain during run" → instant canned answer: stop, see a doctor. The AI never even sees it.
2. **Understanding** (AI). Your messy message — *"work stress 8/10, hot 33C, tight right quad"* — becomes clean data: `stress=8, temp=33C, symptom=quad tightness`. A validator checks the numbers make sense.
3. **The numbers** (code). The bot computes real facts from your history: last 7 days average fatigue, this week's volume vs last week, pace trend. No AI involved.
4. **Book lookup** (RAG). Each expert searches its own library — the runner coach looks up pacing, the physio looks up quad tendonitis — and each pulls the 4 most relevant pages, with sources attached.
5. **Four drafts** (AI, in parallel). Each expert writes its take, using the facts from step 3 and its own book pages.
6. **One answer** (AI). The editor merges the four drafts into a single coherent reply, resolving conflicts (physio wins) and citing sources.
7. **Checking** (code). Citations present? No numbers contradicting the facts? Then it's sent.
8. **Storing** (code). Everything is saved — including all four drafts — so a wrong answer can always be traced to which expert got it wrong.

## 5. How it reads your Strava screenshot

This is the bot's most careful job:

1. **The AI reads the raw numbers** — distance, time, pace, heart rate — and nothing else.
2. **The code does the math.** It computes pace = time ÷ distance by itself. If the AI's read of "pace" doesn't match the code's calculation (within a small tolerance), that number is flagged as untrustworthy.
3. **The code checks the numbers against the plan** — did you do what Saturday's long run asked for?
4. **It reads the numbers back to you:** "I see 5.02 km, 24:59 → 4:58/km. Planned: 5.0 km easy. Correct?"
5. Only after you confirm do the numbers enter your history and stats.

Wrong numbers never sneak in silently. And if reading the screenshot fails twice, the bot simply asks you to type the distance and time — no guessing.

## 6. Why is it slow on purpose?

"Instant" AI answers come from one quick guess. This bot makes **six passes** instead: extract → compute → four experts → merge → verify. Each pass is slower, and some steps ask you to confirm.

That's the point. A training bot that says the wrong pace is worse than one that takes 10 seconds and is right. Fast-but-wrong is the failure mode we're designing against.

## 6.5 A note on the models

The bot uses two models on purpose:

- **DeepSeek V4-Flash** does the talking — cheap and fast, so the "four experts" design (which needs several rounds of thinking per message) stays affordable.
- **A separate small vision model** reads your Strava screenshots, because DeepSeek's API doesn't accept images. It's a specialist: it reads numbers from pictures, and the code still does the math on them.

The plan is built so either model can be swapped without touching the bot's logic — and every swap must re-pass the test suite before it's allowed.

## 7. What is RAG?

RAG = **Retrieval-Augmented Generation**. Simple idea: before answering, the bot looks things up in its own library, like a student opening the textbook before writing the essay.

The AI's memory of training advice is unreliable — it might confidently recommend something made-up. But an answer based on a page it just retrieved, with the source named, is grounded in something real. If there's no matching page, it must say **"I don't have data on that"** — it's not allowed to invent.

Important limit: the library holds only *knowledge* (how to train). Your *personal history* lives in the database, and the numbers are always computed by code.

## 8. What are "training phases"?

Training isn't one long grind. It's seasons:

- **Base** (now → ~Jul 2026): build endurance slowly, gain weight to ~55 kg, get strong. Easy runs.
- **Build** (Jul → Oct 2026): get faster, longer long runs, quality sessions.
- **Peak** (last weeks): sharpest training.
- **Taper** (2–3 weeks before race): run less so you arrive fresh.
- **Race, then Recovery** — then the cycle repeats for race #2.

The bot knows which season you're in. `/today` gives the right workout for the season, and all four experts automatically adjust as the calendar advances. **No manual updates needed.**

## 9. How does the bot stay accurate over months?

Three boring-but-critical mechanisms:

1. **Weekly summaries.** Every Sunday the bot computes a rollup: total km, average fatigue, weight trend. Months of history become small, reliable numbers — so the bot can answer "how has my volume trended?" without reading every old message.
2. **Re-plan gates.** Every 4–6 weeks the bot compares your actual pace trend to the target and *proposes*: "your last 4 weeks suggest 6:55/km is realistic — update the target?" You say yes or no. The plan stays honest because real data drives it.
3. **Tests (the eval suite).** Sample questions with known-correct answers — for each expert, plus trick questions where experts must disagree and physio must win, plus your real Strava screenshots with known values. Every time the prompts, knowledge base, or model changes, the bot must re-pass all samples before the change is allowed.

## 10. What about you quitting?

Honest answer: the biggest risk isn't the AI — it's **you stopping logging** after two months. So the bot works to keep you engaged: a Sunday recap push with your progress, streak awareness, milestone celebrations (first 50 km month). And it never guilt-trips a missed session — it just adjusts the plan.

## 11. One-sentence summary

The bot is **a panel of four coaching experts — runner, calisthenics, mobility, physio — merged into one trainer by an editor who respects safety first**, wrapped in honest math, personal libraries, a seasonal calendar, and self-tests, so that six months from now it still knows exactly where you are and what to do next.
