"""Eval harness + regression gate.

- assert_case / assert_conflict: mechanical checks on an answer (topics,
  forbidden strings, citations, physio priority).
- execute_case: run one case through the full pipeline (generate_reply).
- run_suite: golden + conflict cases → pass/fail report.
- Gate checksums: personas/, knowledge/, model config. ANY change dirties
  the gate — the suite must re-pass before the change ships.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from facts import FactsBlock
from synthesize import generate_reply

CASES_PATH = Path(__file__).resolve().parent / "cases.yaml"
GATE_STATE_PATH = Path(__file__).resolve().parent / ".gate_state.json"
REPO_ROOT = Path(__file__).resolve().parent.parent

CITATION_RE_PATTERN = "[SOURCE:"
NO_DATA_PHRASES = ("no data", "no knowledge-base match", "no knowledge base match")


def load_cases() -> dict:
    with CASES_PATH.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _lower_haystack(answer: str) -> str:
    return answer.lower()


def assert_case(answer: str, case: dict) -> list[str]:
    """Mechanical checks for a golden case. Empty list = pass."""
    problems: list[str] = []
    hay = _lower_haystack(answer)

    for topic in case.get("topics", []):
        if topic.lower() not in hay:
            problems.append(f"missing topic: {topic!r}")
    for forbidden in case.get("forbidden", []):
        if forbidden.lower() in hay:
            problems.append(f"forbidden phrase present: {forbidden!r}")
    if case.get("citation"):
        has_citation = CITATION_RE_PATTERN in answer
        has_no_data = any(phrase in hay for phrase in NO_DATA_PHRASES)
        if not (has_citation or has_no_data):
            problems.append("citation required but missing (no [SOURCE: ...] / no-data)")

    if case.get("physio_wins"):
        physio_sided = any(
            marker in hay for marker in ("rest", "skip", "stop", "physio", "veto", "medical")
        )
        if not physio_sided:
            problems.append("physio priority case — answer does not side with safety")
    return problems


def assert_conflict(answer: str, case: dict) -> list[str]:
    """Conflict cases: same mechanics plus physio_wins handling."""
    return assert_case(answer, case)


def dir_checksum(paths: list[Path]) -> str:
    """Stable content hash over the given files/dirs (sorted, recursive).
    Paths are hashed relative to their own root — portable across machines."""
    digest = hashlib.sha256()
    for path in sorted(paths):
        files = sorted(path.rglob("*")) if path.is_dir() else [path]
        for file in files:
            if not file.is_file():
                continue
            try:
                rel = file.relative_to(path).as_posix()
            except ValueError:
                rel = file.name
            digest.update(rel.encode())
            digest.update(file.read_bytes())
    return digest.hexdigest()


def gate_state(
    *,
    prompt_dir: Path | None = None,
    kb_dir: Path | None = None,
    models: tuple[str, str] = ("", ""),
) -> dict:
    return {
        "personas": dir_checksum([prompt_dir or REPO_ROOT / "personas"]),
        "knowledge": dir_checksum([kb_dir or REPO_ROOT / "knowledge"]),
        "models": list(models),
    }


def gate_dirty(current: dict, baseline: dict | None = None) -> list[str]:
    """Sections that changed vs the baseline (or vs the stored state file)."""
    baseline = baseline or _load_stored_state()
    if baseline is None:
        return ["no baseline recorded — run the suite once to create it"]
    changed = [key for key in ("personas", "knowledge", "models") if baseline.get(key) != current.get(key)]
    return changed


def _load_stored_state() -> dict | None:
    if not GATE_STATE_PATH.exists():
        return None
    return json.loads(GATE_STATE_PATH.read_text(encoding="utf-8"))


def save_gate_state(state: dict) -> None:
    GATE_STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def default_facts() -> FactsBlock:
    return FactsBlock(
        avg_rpe_7d=6.3,
        fatigue_this_week=5.5,
        fatigue_last_week=4.5,
        volume_km_this_week=18.5,
        volume_km_last_week=17.0,
        volume_delta_pct=8.8,
        pace_avg_last3_sec_km=418.0,
        pace_avg_prev3_sec_km=425.0,
        weight_latest_kg=55.4,
        completed_sessions_7d=4,
    )


async def execute_case(
    client,
    personas,
    case: dict,
    *,
    facts: FactsBlock | None = None,
    retrieval_fn=None,
) -> str:
    """Run one case through the full pipeline; returns the final answer."""
    if retrieval_fn is None:
        retrieval_fn = lambda persona_key, message: ""  # noqa: E731
    answer, _ = await generate_reply(
        client,
        personas,
        facts=facts or default_facts(),
        user_message=case["prompt"],
        retrieval_fn=retrieval_fn,
    )
    return answer


async def run_suite(
    client,
    personas,
    *,
    facts: FactsBlock | None = None,
    retrieval_fn=None,
) -> dict:
    """Run all golden + conflict cases. Returns {total, passed, failures}."""
    cases = load_cases()
    results: list[dict] = []
    for case in cases["golden_cases"] + cases["conflict_cases"]:
        answer = await execute_case(client, personas, case, facts=facts, retrieval_fn=retrieval_fn)
        problems = assert_case(answer, case)
        results.append(
            {
                "id": case["id"],
                "persona": case.get("persona"),
                "passed": not problems,
                "problems": problems,
            }
        )
    passed = sum(1 for r in results if r["passed"])
    return {
        "total": len(results),
        "passed": passed,
        "failures": [r for r in results if not r["passed"]],
    }
