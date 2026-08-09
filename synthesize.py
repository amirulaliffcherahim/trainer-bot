"""Synthesis — 4 persona passes concurrently, one merged answer, validated.

Flow per message:

1. `run_persona_passes`: for each persona — `retrieval_fn(persona_key,
   message)` renders its KB section; `compose_persona_messages` builds the
   prompt; ONE `chat_async` call each. All four run CONCURRENTLY via
   `asyncio.gather`. A persona whose call fails (`AllModelsFailed`) yields a
   FAILED placeholder instead of killing the reply.

2. `synthesize`: the editor pass merges the drafts under the conflict
   hierarchy (physio > runner > calisthenics > mobility), preserving
   `[SOURCE: ...]` citations and surfacing conflicts explicitly.

3. `generate_reply`: orchestrates 1 → 2 → validation. On failure, ONE
   corrective editor pass receives the flagged problems. If every persona
   pass failed, `AllModelsFailed` propagates — caller switches to degraded
   mode.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass

from facts import FactsBlock, format_facts_block
from llm_client import AllModelsFailed, LLMClient
from personas import PersonaConfig, compose_persona_messages
from validate import validate_reply

log = logging.getLogger(__name__)

PERSONA_TEMPERATURE = 0.3
EDITOR_TEMPERATURE = 0.3

_HEADER_RE = re.compile(r"^#{1,6}\s+.*$", re.MULTILINE)
_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
_ITALIC_RE = re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)")


def polish_reply(text: str) -> str:
    """Deterministic cleanup: strip markdown headers/bold/italics, collapse
    whitespace. Keeps [SOURCE: ...] citations intact."""
    out = _HEADER_RE.sub("", text)
    out = _BOLD_RE.sub(r"\1", out)
    out = _ITALIC_RE.sub(r"\1", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    out = re.sub(r"[ \t]+\n", "\n", out)
    return out.strip()

EDITOR_SYSTEM_PROMPT = """\
You are the EDITOR of a coaching panel for a half-marathon athlete. Four
expert drafts follow, each written by a specialist with its own knowledge
base.

Conflict hierarchy (highest authority first):
1. Physiotherapy Trainer — safety; may veto anything
2. Distance Runner Trainer — training load
3. Calisthenics Trainer — strength work
4. Mobility Trainer — supplementary

Rules:
- Merge the drafts into ONE reply in the athlete's ear. The four experts
  are your INTERNAL thinking — their knowledge becomes YOURS.
- NEVER attribute advice to a persona: no "the physio says", no "the
  runner coach recommends", no expert names in the reply. Say it as your
  own call: "we're skipping the long run", "your quad needs a rest day",
  "I'd drop the tempo this week".
- When a higher-authority expert contradicts a lower one, the higher
  authority wins — and the conflict MUST be surfaced and owned in first
  person (e.g. "we're resting today — your quad wins over the mileage").
  Never silently drop a contradiction; never name the expert.
- Preserve every [SOURCE: ...] citation from the drafts that you use. Cite
  in the same form: [SOURCE: title].
- Do not invent numbers. The CURRENT STATE block is ground truth — use its
  numbers as-is, never recompute.
- If every draft reports no knowledge-base match, say you have no data on
  that topic rather than improvising.
- If a draft is marked [PASS FAILED], ignore it.

Tone — you are the athlete's coach:
- Reply as ONE person in your own voice. Never mention personas, drafts,
  commands, or that you are a bot or assistant. Never say "as your
  trainer/coach" — just be it.
- Talk like you know them: "you/we", short lines, match their energy.
  Casual check-in → casual reply; grumble → empathy first, then the fix.
- Warm, direct, human. No corporate filler, no lecturing, no emoji spam.
  The chill delivery never changes the numbers or the safety rules.
- When natural, end with ONE light follow-up question to keep the chat
  going (at most one — never on safety-critical answers).

Output format (non-negotiable):
- Plain conversational paragraphs. NO markdown headers, NO bold or
  italics, no code blocks.
- Max ~3 short paragraphs; bullets only when listing 3+ items, as plain
  dashes.
- No filler openers ("Great question!", "That's a good point"), no
  sign-offs, no "Sure!", no "Here's what I recommend:" — start with the
  answer, the way a coach would say it out loud.
- Keep [SOURCE: title] citations inline where you use them.
- Output only the final reply, plain text, no preamble.
"""

EXPLAIN_ADDENDUM = """\
EXPLAIN MODE — the athlete asked why / how / to elaborate.
Go DEEP: give the mechanism, the background, the trade-offs, the 'because'
behind each recommendation. Teach the reasoning, not just the rule. Still
cite sources and keep the chill tone — deep doesn't mean dense.
"""


@dataclass
class PersonaDraft:
    key: str
    name: str
    content: str | None  # None = pass failed
    kb_section: str  # rendered KB, "" = no match
    veto_level: int


async def run_persona_passes(
    client: LLMClient,
    personas: dict[str, PersonaConfig],
    *,
    facts: FactsBlock,
    user_message: str,
    retrieval_fn,
    profile_str: str = "",
) -> dict[str, PersonaDraft]:
    """Run the 4 persona passes concurrently.

    retrieval_fn(persona_key, user_message) -> rendered KB section ("" when
    no match). facts formatting happens here, once.
    """
    facts_str = format_facts_block(facts)
    if profile_str:
        facts_str += "\n\n" + profile_str

    async def _one(persona: PersonaConfig) -> PersonaDraft:
        kb_section = retrieval_fn(persona.key, user_message)
        messages = compose_persona_messages(
            persona,
            facts_block=facts_str,
            kb_section=kb_section,
            user_message=user_message,
        )
        try:
            content = await client.chat_async(messages, temperature=PERSONA_TEMPERATURE)
        except AllModelsFailed as exc:
            log.warning("Persona pass %s failed: %s", persona.key, exc)
            content = None
        return PersonaDraft(
            key=persona.key,
            name=persona.name,
            content=content,
            kb_section=kb_section,
            veto_level=persona.veto_level,
        )

    results = await asyncio.gather(*(_one(p) for p in personas.values()))
    return {draft.key: draft for draft in results}


def _render_drafts(drafts: dict[str, PersonaDraft]) -> str:
    """Drafts in authority order (highest veto first)."""
    ordered = sorted(drafts.values(), key=lambda d: -d.veto_level)
    parts: list[str] = []
    for draft in ordered:
        header = f"### {draft.name} ({draft.key})"
        if draft.content is None:
            parts.append(f"{header}\n[PASS FAILED — no model response]")
        else:
            parts.append(f"{header}\n{draft.content}")
    return "\n\n".join(parts)


async def synthesize(
    client: LLMClient,
    drafts: dict[str, PersonaDraft],
    *,
    facts_block_str: str,
    explain: bool = False,
) -> str:
    """One editor pass merging all persona drafts. explain=True adds the
    deep-dive directive (user asked why/how)."""
    rendered = _render_drafts(drafts)
    system_prompt = EDITOR_SYSTEM_PROMPT + (EXPLAIN_ADDENDUM if explain else "")
    user = f"CURRENT STATE (ground truth):\n{facts_block_str}\n\n{rendered}"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user},
    ]
    return await client.chat_async(
        messages,
        temperature=EDITOR_TEMPERATURE,
        thinking=True,
        reasoning_effort="high",
    )


async def _synthesize_corrective(
    client: LLMClient,
    drafts: dict[str, PersonaDraft],
    *,
    facts_block_str: str,
    problems: list[str],
) -> str:
    rendered = _render_drafts(drafts)
    user = (
        f"CURRENT STATE (ground truth):\n{facts_block_str}\n\n{rendered}\n\n"
        "Your previous draft was rejected for:\n- "
        + "\n- ".join(problems)
        + "\nFix exactly those issues. Keep citations where used; do not "
        "invent numbers."
    )
    messages = [
        {"role": "system", "content": EDITOR_SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]
    return await client.chat_async(
        messages,
        temperature=EDITOR_TEMPERATURE,
        thinking=True,
        reasoning_effort="high",
    )


async def generate_reply(
    client: LLMClient,
    personas: dict[str, PersonaConfig],
    *,
    facts: FactsBlock,
    user_message: str,
    retrieval_fn,
    profile_str: str = "",
    explain: bool = False,
    knowledge_seeking: bool = True,
) -> tuple[str, dict[str, PersonaDraft]]:
    """Full synthesis pipeline: persona passes → editor → validation, with
    one corrective editor pass on validation failure. explain=True deep-dives.
    knowledge_seeking=False skips the 'no data' requirement (routine logs)."""
    drafts = await run_persona_passes(
        client,
        personas,
        facts=facts,
        user_message=user_message,
        retrieval_fn=retrieval_fn,
        profile_str=profile_str,
    )
    if all(draft.content is None for draft in drafts.values()):
        raise AllModelsFailed("all persona passes failed — use degraded mode")

    facts_str = format_facts_block(facts)
    answer = await synthesize(
        client, drafts, facts_block_str=facts_str, explain=explain
    )
    answer = polish_reply(answer)

    result = validate_reply(
        answer, facts_block=facts, drafts=drafts, knowledge_seeking=knowledge_seeking
    )
    if not result.valid:
        log.info("Synthesis failed validation: %s", result.problems)
        answer = polish_reply(
            await _synthesize_corrective(
                client,
                drafts,
                facts_block_str=facts_str,
                problems=result.problems,
            )
        )
    return answer, drafts
