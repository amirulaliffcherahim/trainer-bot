"""synthesize.py tests — concurrent persona passes, editor merge, corrective
loop (mocked LLM, no network)."""

import pytest

from facts import FactsBlock
from llm_client import AllModelsFailed
from personas import load_personas
from synthesize import generate_reply, run_persona_passes, synthesize


class FakeLLMClient:
    """Scripted chat_async responses; records every call."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    async def chat_async(self, messages, **kwargs):
        self.calls.append({"messages": messages, **kwargs})
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


FACTS = FactsBlock(
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

PERSONAS = load_personas()

CITED_REPLY = "Rest today, then easy 5 km. [SOURCE: triage.md]"


def _retrieval_fn(persona_key: str, user_message: str) -> str:
    return "- [SOURCE: triage.md] red flags" if persona_key == "physio" else ""


@pytest.mark.asyncio
async def test_four_passes_run_concurrently() -> None:
    client = FakeLLMClient(["draft"] * 4)
    drafts = await run_persona_passes(
        client, PERSONAS, facts=FACTS, user_message="legs tired", retrieval_fn=_retrieval_fn
    )
    assert set(drafts) == {"runner", "calisthenics", "mobility", "physio"}
    assert len(client.calls) == 4
    assert all(call["temperature"] == 0.3 for call in client.calls)
    # Each pass got its own role prompt + the facts block.
    for call in client.calls:
        system = call["messages"][0]["content"]
        assert "Current state" in system
    runner_system = client.calls[0]["messages"][0]["content"]
    assert "DISTANCE RUNNER TRAINER" in runner_system


@pytest.mark.asyncio
async def test_profile_snapshot_injected_into_passes() -> None:
    client = FakeLLMClient(["draft"] * 4)
    await run_persona_passes(
        client, PERSONAS, facts=FACTS, user_message="hi",
        retrieval_fn=lambda k, m: "",
        profile_str="## Profile\nheight 175 cm, VO2 max n/a",
    )
    for call in client.calls:
        assert "VO2 max n/a" in call["messages"][0]["content"]


@pytest.mark.asyncio
async def test_failed_persona_pass_becomes_placeholder() -> None:
    script = ["runner draft", AllModelsFailed("down"), "mobility draft", "physio draft"]
    client = FakeLLMClient(script)
    drafts = await run_persona_passes(
        client, PERSONAS, facts=FACTS, user_message="hi", retrieval_fn=lambda k, m: ""
    )
    assert drafts["calisthenics"].content is None
    assert drafts["runner"].content == "runner draft"


@pytest.mark.asyncio
async def test_editor_merges_with_hierarchy_and_citations() -> None:
    client = FakeLLMClient(["draft"] * 4 + ["final answer"])
    drafts = await run_persona_passes(
        client, PERSONAS, facts=FACTS, user_message="hi", retrieval_fn=_retrieval_fn
    )
    answer = await synthesize(
        client, drafts, facts_block_str="## Current state\n- x"
    )
    assert answer == "final answer"
    editor = client.calls[4]
    system = editor["messages"][0]["content"]
    assert "Conflict hierarchy" in system
    assert "Physiotherapy Trainer" in system  # authority listed first
    assert "surfaced explicitly" in system
    assert "[SOURCE:" in system  # citation preservation instructed
    assert "knowledgeable mate" in system  # chill tone directive
    user = editor["messages"][1]["content"]
    assert "physio" in user and "runner" in user and "calisthenics" in user and "mobility" in user
    assert "CURRENT STATE" in user


@pytest.mark.asyncio
async def test_explain_mode_adds_deep_dive_directive() -> None:
    client = FakeLLMClient(["draft"] * 4 + ["final answer"])
    drafts = await run_persona_passes(
        client, PERSONAS, facts=FACTS, user_message="why taper?", retrieval_fn=_retrieval_fn
    )
    await synthesize(
        client, drafts, facts_block_str="## Current state\n- x", explain=True
    )
    system = client.calls[4]["messages"][0]["content"]
    assert "EXPLAIN MODE" in system
    assert "Go DEEP" in system


@pytest.mark.asyncio
async def test_no_explain_mode_by_default() -> None:
    client = FakeLLMClient(["draft"] * 4 + ["final answer"])
    drafts = await run_persona_passes(
        client, PERSONAS, facts=FACTS, user_message="hi", retrieval_fn=_retrieval_fn
    )
    await synthesize(client, drafts, facts_block_str="## Current state\n- x")
    system = client.calls[4]["messages"][0]["content"]
    assert "EXPLAIN MODE" not in system
    assert "Depth is served on request" in system


@pytest.mark.asyncio
async def test_generate_reply_valid_first_try() -> None:
    client = FakeLLMClient(["draft"] * 4 + [CITED_REPLY])
    answer, drafts = await generate_reply(
        client, PERSONAS, facts=FACTS, user_message="hi", retrieval_fn=_retrieval_fn
    )
    assert answer == CITED_REPLY
    assert len(client.calls) == 5  # 4 persona + 1 editor


@pytest.mark.asyncio
async def test_generate_reply_corrective_loop() -> None:
    # Editor 1: no citation (physio had KB) → rejected → corrective editor 2.
    client = FakeLLMClient(["draft"] * 4 + ["run the long run tomorrow", CITED_REPLY])
    answer, _ = await generate_reply(
        client, PERSONAS, facts=FACTS, user_message="hi", retrieval_fn=_retrieval_fn
    )
    assert answer == CITED_REPLY
    assert len(client.calls) == 6  # 4 persona + 2 editor
    corrective = client.calls[5]["messages"][1]["content"]
    assert "rejected for" in corrective
    assert "SOURCE" in corrective


@pytest.mark.asyncio
async def test_all_passes_fail_propagates() -> None:
    client = FakeLLMClient([AllModelsFailed("down")] * 4)
    with pytest.raises(AllModelsFailed):
        await generate_reply(
            client, PERSONAS, facts=FACTS, user_message="hi", retrieval_fn=lambda k, m: ""
        )


@pytest.mark.asyncio
async def test_hierarchy_order_in_render() -> None:
    """Drafts render physio first regardless of dict order."""
    from synthesize import _render_drafts, PersonaDraft

    drafts = {
        "runner": PersonaDraft("runner", "Distance Runner Trainer", "r", "", 3),
        "physio": PersonaDraft("physio", "Physiotherapy Trainer", "p", "", 4),
        "mobility": PersonaDraft("mobility", "Mobility Trainer", "m", "", 1),
    }
    rendered = _render_drafts(drafts)
    assert rendered.index("Physiotherapy Trainer") < rendered.index("Distance Runner Trainer")
