"""Persona configuration — each persona is a markdown file with front matter.

personas/<key>.md:
---
name: <display name>
signals: comma-separated relevance keywords
veto_level: 1-4 (physio = 4, highest)
---
<role prompt body>

compose_persona_messages() builds the per-persona system prompt (role +
facts block + retrieved KB). Phase 4 runs four of these concurrently with
asyncio.gather — this module is the shared contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PERSONA_DIR = Path(__file__).resolve().parent / "personas"
PERSONA_KEYS = ("runner", "calisthenics", "mobility", "physio")


class PersonaError(RuntimeError):
    """Invalid persona file (missing front matter, bad veto_level, ...)."""


@dataclass(frozen=True)
class PersonaConfig:
    key: str
    name: str
    signals: tuple[str, ...]
    veto_level: int
    role_prompt: str


def _parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        raise PersonaError("persona file missing front matter")
    try:
        end = text.index("\n---", 3)
    except ValueError as exc:
        raise PersonaError("persona file front matter not closed") from exc
    header, body = text[3:end], text[end + 4 :].strip()
    meta: dict[str, str] = {}
    for line in header.strip().splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return meta, body


def load_persona(key: str) -> PersonaConfig:
    path = PERSONA_DIR / f"{key}.md"
    if not path.exists():
        raise PersonaError(f"persona file not found: {path}")
    meta, body = _parse_front_matter(path.read_text(encoding="utf-8"))
    try:
        veto_level = int(meta.get("veto_level", "1"))
    except ValueError as exc:
        raise PersonaError(f"persona {key}: invalid veto_level") from exc
    return PersonaConfig(
        key=key,
        name=meta.get("name", key),
        signals=tuple(s.strip() for s in meta.get("signals", "").split(",") if s.strip()),
        veto_level=veto_level,
        role_prompt=body,
    )


def load_personas() -> dict[str, PersonaConfig]:
    return {key: load_persona(key) for key in PERSONA_KEYS}


def compose_persona_messages(
    persona: PersonaConfig,
    *,
    facts_block: str,
    kb_section: str,
    user_message: str,
) -> list[dict[str, str]]:
    """Build the message list for one persona pass.

    kb_section: rendered retrieval results (or "" when no match — the
    persona must then say "no data", never invent).
    """
    system = persona.role_prompt + "\n\n" + facts_block
    if kb_section:
        system += "\n\n## Knowledge base — cite [SOURCE: title] when you use these\n" + kb_section
    else:
        system += "\n\n## Knowledge base\nNo knowledge-base match for this topic. Say so — do not invent guidance."
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_message},
    ]
