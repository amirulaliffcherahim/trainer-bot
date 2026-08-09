"""test_eval_gate.py — case loading, assertion mechanics, regression gate,
synthetic-image OCR accuracy (guarded), suite mechanics (no network)."""

import io

import pytest

from eval.runner import (
    assert_case,
    dir_checksum,
    execute_case,
    gate_dirty,
    gate_state,
    load_cases,
    run_suite,
)
from eval.synthetic_images import SyntheticRun, ground_truth_text, render
from personas import load_personas

CITED = "Rest today, easy pace. [SOURCE: triage.md]"


def test_case_counts() -> None:
    cases = load_cases()
    goldens = cases["golden_cases"]
    conflicts = cases["conflict_cases"]
    assert len(goldens) >= 32  # 8+ per persona
    assert len(conflicts) >= 10
    personas = {c["persona"] for c in goldens}
    assert personas == {"runner", "calisthenics", "mobility", "physio"}


def test_assert_case_good_answer_passes() -> None:
    case = load_cases()["golden_cases"][0]  # runner-001
    answer = "Keep the long run easy at pace 7:40-8:10 — stop if anything hurts. [SOURCE: pacing.md]"
    assert assert_case(answer, case) == []


def test_assert_case_missing_topic_fails() -> None:
    case = load_cases()["golden_cases"][0]
    assert assert_case("Just rest.", case) != []


def test_assert_case_forbidden_phrase_fails() -> None:
    case = load_cases()["golden_cases"][0]
    answer = "Long run tomorrow — even if it hurts, run through pain. [SOURCE: pacing.md]"
    problems = assert_case(answer, case)
    assert any("forbidden" in p for p in problems)


def test_assert_case_citation_required() -> None:
    case = load_cases()["golden_cases"][0]
    assert assert_case("Do the long run easy.", case) != []  # no citation


def test_conflict_case_physio_wins() -> None:
    case = load_cases()["conflict_cases"][0]  # quad flare + long run
    good = "Physio rule: rest. Skip tomorrow's long run — the tendon wins today. [SOURCE: quad_tendonitis.md]"
    assert assert_case(good, case) == []
    bad = "Do the long run tomorrow — the plan matters."
    assert assert_case(bad, case) != []


def test_conflict_case_physio_not_required_when_false() -> None:
    cases = load_cases()["conflict_cases"]
    non_veto = next(c for c in cases if not c.get("physio_wins"))  # tight quad + tempo
    answer = "Quad is tight — warm up well and keep the tempo easy. [SOURCE: triage.md]"
    assert assert_case(answer, non_veto) == []


def test_gate_dirty_on_prompt_change(tmp_path) -> None:
    prompt_dir = tmp_path / "personas"
    prompt_dir.mkdir()
    (prompt_dir / "runner.md").write_text("role: runner v1")
    kb_dir = tmp_path / "knowledge"
    kb_dir.mkdir()
    state = gate_state(prompt_dir=prompt_dir, kb_dir=kb_dir, models=("flash", "pro"))
    assert gate_dirty(state, baseline=state) == []

    (prompt_dir / "runner.md").write_text("role: runner v2 — deliberately worse")
    changed = gate_dirty(
        gate_state(prompt_dir=prompt_dir, kb_dir=kb_dir, models=("flash", "pro")),
        baseline=state,
    )
    assert "personas" in changed  # the bad prompt change is caught


def test_gate_dirty_on_model_change(tmp_path) -> None:
    state = gate_state(prompt_dir=tmp_path, kb_dir=tmp_path, models=("flash", "pro"))
    new = gate_state(prompt_dir=tmp_path, kb_dir=tmp_path, models=("flash", "pro-2"))
    assert gate_dirty(new, baseline=state) == ["models"]


def test_dir_checksum_stable_and_sensitive(tmp_path) -> None:
    d = tmp_path / "kb"
    d.mkdir()
    (d / "a.md").write_text("one")
    first = dir_checksum([d])
    assert dir_checksum([d]) == first  # stable
    (d / "a.md").write_text("two")
    assert dir_checksum([d]) != first  # sensitive


def test_synthetic_image_ground_truth_roundtrip() -> None:
    run = SyntheticRun(
        title="Saturday Long Run",
        distance_km=10.42,
        moving_time_min=72.6,
        pace_text="6:58",
        avg_hr=124,
        elevation_m=102,
        date="2026-07-11",
    )
    truth = ground_truth_text(run)
    assert "10.42" in truth
    assert "72:36" in truth  # 72.6 min → 72 min 36 s
    assert "6:58" in truth
    assert "124" in truth
    image_bytes = render(run)
    assert image_bytes[:8] == b"\x89PNG\r\n\x1a\n"  # valid PNG


def test_synthetic_image_ocr_accuracy() -> None:
    """Real easyocr over a synthetic image — skipped when the model isn't
    available (first run downloads it)."""
    easyocr = pytest.importorskip("easyocr")
    try:
        reader = easyocr.Reader(["en"], gpu=False, verbose=False)
    except Exception as exc:  # noqa: BLE001 — model download/network failure
        pytest.skip(f"easyocr model unavailable: {exc}")
    run = SyntheticRun(
        title="Saturday Long Run",
        distance_km=10.42,
        moving_time_min=72.6,
        pace_text="6:58",
        avg_hr=124,
    )
    results = reader.readtext(render(run), detail=0, paragraph=True)
    text = " ".join(results)
    assert "10.42" in text
    # OCR punctuation drift is expected (colon → period); the numbers must
    # survive — the pipeline's parse step handles either form.
    assert ("6:58" in text) or ("6.58" in text)
    assert "124" in text


def test_run_suite_mechanics_with_fake_answers() -> None:
    """The harness runs every case and reports failures mechanically."""
    from eval.runner import default_facts

    class PipelineClient:
        def __init__(self):
            self.answers = {}

        async def chat_async(self, messages, **kwargs):
            # persona passes return short drafts; editor returns the case answer
            system = messages[0]["content"]
            if "EDITOR" in system or "EDITOR of a coaching panel" in system:
                return self.editor_answer
            return "draft"

        async def chat_json_async(self, messages, **kwargs):
            return {}

    client = PipelineClient()
    client.editor_answer = "Rest today. [SOURCE: triage.md]"

    import asyncio

    report = asyncio.run(
        run_suite(client, load_personas(), facts=default_facts())
    )
    assert report["total"] >= 42
    # The harness must flag answers that fail — "Rest today." alone fails
    # most golden cases (missing topics/citations), proving the gate bites.
    assert report["passed"] < report["total"]
    assert all("missing topic" in " ".join(f["problems"]) for f in report["failures"])


def test_execute_case_returns_answer() -> None:
    class Client:
        async def chat_async(self, messages, **kwargs):
            return CITED

        async def chat_json_async(self, messages, **kwargs):
            return {}

    import asyncio

    case = load_cases()["golden_cases"][0]
    answer = asyncio.run(execute_case(Client(), load_personas(), case))
    assert answer == CITED
