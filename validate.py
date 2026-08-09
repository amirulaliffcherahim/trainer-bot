"""Output validation — code-level checks on the synthesized reply.

Two rule groups:

1. **Citation honesty.** If any persona draft used knowledge-base chunks, the
   reply must cite `[SOURCE: ...]`. If no KB matched anywhere, the reply must
   contain a "no data" statement — the model is never allowed to improvise.

2. **Number consistency with the facts block.** Plain numeric tokens in the
   reply that land within 5% of a known fact value must match it (within
   0.5%); a near-miss is treated as a misquote — the classic LLM error mode
   is "close but wrong" (e.g. "18.0 km" when the facts say 18.5).

   Deliberate heuristic limits: pace strings (m:ss) are NOT checked — target
   and planned paces legitimately differ from achieved pace facts, and
   context-free matching can't tell them apart. The corrective pass still
   re-prompts the editor with flagged problems.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from facts import FactsBlock

CITATION_RE = re.compile(r"\[SOURCE:\s*[^\]]+\]", re.IGNORECASE)
NO_DATA_PHRASES = (
    "no data",
    "no knowledge-base match",
    "no knowledge base match",
    "don't have data",
    "i don't have data",
    "no information on",
    "not in my knowledge base",
)
# Question-ish messages seek knowledge; routine logs ("easy 5k done") don't.
QUESTION_RE = re.compile(
    r"\b(why|what|how|when|which|should|can|explain|kenapa|macam mana|bagaimana|recommend|suggest|is it|does)\b",
    re.IGNORECASE,
)
_NUM_RE = re.compile(r"\d+(?:\.\d+)?")
_NEAR = 0.05  # within 5% of a fact → must match
_EQUAL = 0.005  # within 0.5% counts as matching
_MIN_REPLY_LEN = 20


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    problems: list[str] = field(default_factory=list)


def _numeric_facts(facts: FactsBlock) -> list[tuple[str, float]]:
    candidates = (
        ("7-day average RPE", facts.avg_rpe_7d),
        ("this-week fatigue", facts.fatigue_this_week),
        ("weekly volume (km)", facts.volume_km_this_week),
        ("last-week volume (km)", facts.volume_km_last_week),
        ("latest weight (kg)", facts.weight_latest_kg),
    )
    return [(label, value) for label, value in candidates if value is not None]


def _number_problems(reply: str, facts: FactsBlock) -> list[str]:
    problems: list[str] = []
    known = _numeric_facts(facts)
    for token in _NUM_RE.findall(reply):
        value = float(token)
        for label, fact in known:
            if fact == 0:
                continue
            relative = abs(value - fact) / fact
            if _NEAR >= relative > _EQUAL:
                problems.append(
                    f"number {token} is near the fact '{label}' ({fact}) but differs — "
                    "check the value or drop it"
                )
    return problems


def is_knowledge_seeking(text: str) -> bool:
    """True for question-like messages — the only ones the 'no data'
    honesty rule applies to. Routine logs and acknowledgments are exempt."""
    return "?" in text or bool(QUESTION_RE.search(text))


def validate_reply(
    reply: str,
    *,
    facts_block: FactsBlock,
    drafts: dict,
    knowledge_seeking: bool = True,
) -> ValidationResult:
    """Validate a synthesized reply. `drafts` maps persona key → draft object
    exposing `.kb_section` ("" when nothing was retrieved for that persona).

    knowledge_seeking=False (routine log/ack): the 'no data' requirement is
    skipped — a reply to "easy 5k done" must not be forced to say it has no
    data. Citations are still required whenever KB was actually used.
    """
    problems: list[str] = []

    stripped = reply.strip() if reply else ""
    if len(stripped) < _MIN_REPLY_LEN:
        problems.append("reply is empty or too short")

    had_kb = any(draft.kb_section for draft in drafts.values())
    has_citation = bool(CITATION_RE.search(stripped))
    has_no_data = any(phrase in stripped.lower() for phrase in NO_DATA_PHRASES)

    if had_kb and not has_citation:
        problems.append(
            "drafts used knowledge-base chunks but the reply cites no [SOURCE: ...]"
        )
    if knowledge_seeking and not had_kb and not has_no_data:
        problems.append(
            "no knowledge-base match, but the reply does not state it has no data"
        )

    problems.extend(_number_problems(stripped, facts_block))

    return ValidationResult(valid=not problems, problems=problems)
