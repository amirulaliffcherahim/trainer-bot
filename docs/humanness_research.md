# What Makes a Chatbot Feel Human — Research Notes

Sources: arXiv studies, CHI/HCI literature, Microsoft HAX guidelines.
Mapped to this bot's architecture with status per item.

## 1. Delivery beats content (Iizuka & Mori, IEEE Access 2022)

Spontaneous, natural delivery generates measurably more human perception
(shorter response latency from users, more backchannels, "closer to human
conversation" ratings). Written-bot phrasing ("Here's what I recommend:")
reads like read speech — robotic.

**Status:** editor prompt bans filler openers and app-speak; prelude
interjections provide natural pacing. → keep tightening delivery, not
features.

## 2. Fast + slow thinking (DUMA, Tian et al. 2023)

A dual-mind agent (fast intuitive model + slow deliberate model invoked
only when needed) balances responsiveness and quality. Monotonic
agents — same depth for everything — feel robotic.

**Status:** implemented. Routine logs → single fast call; questions and
symptoms → full 4-persona + editor + reasoning pass. This architecture is
now research-backed.

## 3. Two-stage emotional response (Think Twice, Qian et al., AAMAS 2023)

Separating semantic generation from an emotion-refinement stage produces
responses that are both correct and emotionally appropriate — joint
models generate "safe" (flat) responses.

**Status:** implemented — persona drafts (content) + editor (voice/merge)
is the same two-stage shape.

## 4. Style matching (Aneja et al., CHI 2019)

Agents that adapt to the interlocutor's conversational style are rated
more natural; monotonic style is a core gap. Short message → short reply;
grumble → empathy first.

**Status:** partially — editor instructed to "match their energy". Gap:
language matching (Malay/rojak reply when user writes Malay).

## 5. Repair & grounding (Clark et al., CHI 2019; Schegloff)

Human conversation constantly repairs misunderstandings and grounds
understanding (echoing back what was heard). Agents that repair feel
human; agents that never admit error feel alien.

**Status:** strong — corrective re-prompts, Strava echo-confirm ("Read:
10.42 km… Correct?"), "glitched for a sec" error handler.

## 6. HAX Guidelines for Human-AI Interaction (Amershi et al., CHI 2019 — award-winning)

The canonical 18 guidelines; the humanness-relevant subset:

| Guideline | Status |
|---|---|
| G5: Match relevant social norms | Done — coach voice, no app-speak |
| G9: Support efficient correction / explain why | Done — echo-confirm, citations, replan proposals |
| G10: Communicate clearly what it can't do | Done — "no data on that", degraded mode |
| G15: Remember recent interactions | Done — rolling facts, date recall |
| G17: Avoid overstating capabilities | Done — honest no-data, ±5% prediction bands |
| G18: Convey consequences of actions | Partial — replan proposals say why |

## 7. Memory & continuity (HAX G15; Nass & Moon CASA 2000)

People apply human social rules to computers: reciprocity, consistency,
remembering. Forgetting what was said two messages ago reads as
non-human. Long-term coherence of identity and advice is a top humanness
signal.

**Status:** facts block + weekly rollups + date recall cover recency. Gap:
no recall of the bot's OWN last advice ("you said rest yesterday") —
future work: store last advice summary, inject into prompts.

## Open gaps (ranked)

1. **Language matching** — reply in the user's language (Malay/rojak if
   they write it). One-line editor prompt change.
2. **Backchannels** — occasional light acknowledgment openings ("yeah —",
   "got it —") increase perceived humanness (Iizuka). Editor prompt tweak.
3. **Self-consistency recall** — bot remembering its own previous advice
   across days (store last advice, include in facts block).
4. **Deeper style matching** — short user message → ≤2 lines; long/venting
   → fuller reply (mostly handled by fast path + explain mode).

## Sources

- Iizuka & Mori, "How does a spontaneously speaking conversational agent
  affect user behavior?", IEEE Access 10 (2022) — arXiv:2205.00755
- Tian et al., "DUMA: Dual-Mind Conversational Agent with Fast and Slow
  Thinking", 2023 — arXiv:2310.18075
- Qian et al., "Think Twice: A Human-like Two-stage Conversational Agent",
  AAMAS 2023 — arXiv:2301.04907
- Aneja et al., "Designing Style Matching Conversational Agents", CHI 2019
  workshop — arXiv:1910.07514
- Fadhil et al., "CoachAI: A Conversational Agent Assisted Health Coaching
  Platform", 2019 — arXiv:1904.11961 (health-coach chatbot validation)
- Amershi et al., "Guidelines for Human-AI Interaction", CHI 2019 —
  https://www.microsoft.com/en-us/haxtoolkit/ai-guidelines/
- Clark et al., "What Makes a Good Conversation? Challenges in Designing
  Truly Conversational Agents", CHI 2019
- Nass & Moon, "Machines and Mindlessness: Social Responses to Computers",
  Journal of Social Issues (2000)
