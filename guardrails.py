"""Guardrails — code-level rules evaluated BEFORE any AI call.

Design: red flags short-circuit the LLM entirely with canned responses
(physio-safety first). Volume caps are enforced here, in code, never via
prompt. Security note: the allowlist gate runs before this module in the
handler; this module protects the allowed user from bad advice.

Caveat: rules are keyword/regex-based and conservative — a message like "no
sharp pain today" WILL trip the acute_injury rule. False positives err on
the side of safety; the user can clarify in the follow-up.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

RED_FLAG_RULES: tuple[tuple[str, str, str], ...] = (
    (
        "cardiac",
        r"\b(chest pain|chest tightness|pressure in (the )?chest|heart palpitations)\b",
        "🚨 Stop exercising immediately. Chest pain or pressure during/after "
        "exercise requires medical evaluation — call for help or go to the "
        "nearest clinic/emergency. Do not 'test it out'. This overrides all "
        "training advice.",
    ),
    (
        "breathing",
        r"\b(difficulty breathing|shortness of breath at rest|can'?t breathe)\b",
        "🚨 Stop. Difficulty breathing at rest is a medical red flag — see a "
        "doctor today. Do not run until cleared.",
    ),
    (
        "collapse",
        r"\b(faint(ed|ing)?|collaps(e|ed)|blacked out|passed out)\b",
        "🚨 Fainting or collapse during exercise requires medical evaluation — "
        "do not resume training until a doctor clears you.",
    ),
    (
        "fever",
        r"\b(fever|temperature|flu|sick with)\b",
        "🛑 Rest. Training with a fever or active illness increases cardiac "
        "risk and delays recovery. Return only when symptom-free for 24–48 h. "
        "See a doctor if the fever persists beyond 3 days.",
    ),
    (
        "acute_injury",
        r"\b(can'?t weight.?bear|sharp pain|popping? (sound|sensation)|"
        r"swelling.*(knee|ankle|joint)|numbness|tingling)\b",
        "🛑 Stop the aggravating activity. Sharp pain, swelling, numbness, or "
        "a pop warrants professional assessment — this is beyond "
        "self-coaching. Rest today; see a physio or doctor.",
    ),
)


@dataclass(frozen=True)
class GuardrailResult:
    triggered: bool
    rule_id: str | None = None
    response: str | None = None


def evaluate_guardrails(user_text: str) -> GuardrailResult:
    """First matching red-flag rule wins. Untriggered = safe to proceed."""
    text = user_text.lower()
    for rule_id, pattern, response in RED_FLAG_RULES:
        if re.search(pattern, text):
            return GuardrailResult(triggered=True, rule_id=rule_id, response=response)
    return GuardrailResult(triggered=False)


def volume_increase_within_cap(
    new_week_km: float, prev_week_km: float, cap_pct: float = 10.0
) -> bool:
    """The ≤10%/week hard cap. No previous baseline → allowed."""
    if prev_week_km <= 0:
        return True
    pct = (new_week_km - prev_week_km) / prev_week_km * 100.0
    return pct <= cap_pct


SYMPTOM_KEYWORDS = frozenset(
    {
        "quad", "shin", "knee", "calf", "achilles", "ankle", "hip",
        "hamstring", "heel", "pain", "tight", "sore", "ache", "tendonitis",
        "swelling", "betis", "peha", "sengal", "lenguh", "ketat", "kaku",
        "koyak", "lemau", "numb", "tingling",
    }
)


def has_symptom_signals(user_text: str) -> bool:
    """Weighting signal for the physio/mobility personas (Phase 4)."""
    text = user_text.lower()
    return any(keyword in text for keyword in SYMPTOM_KEYWORDS)
