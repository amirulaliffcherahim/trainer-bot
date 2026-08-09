"""Handler-level tests — run the REAL handle_text with fakes. Catches
runtime-only bugs (unqualified names, wrong params) that unit tests of the
pieces miss."""

import asyncio
from types import SimpleNamespace

import pytest

import bot as bot_module
from config import Settings
from db import init_db


class FakeMessage:
    def __init__(self, text: str | None = None, caption: str | None = None):
        self.text = text
        self.caption = caption
        self.photo = []
        self.sent: list[str] = []
        self.edited: list[str] = []

    async def reply_text(self, text, **kwargs):
        self.sent.append(text)
        return self

    async def edit_text(self, text, **kwargs):
        self.edited.append(text)


class FakeUser:
    id = 1


class FakeUpdate:
    def __init__(self, message: FakeMessage):
        self.message = message
        self.effective_user = FakeUser()


class FakeContext:
    def __init__(self, conn, client):
        self.bot_data = {
            "settings": Settings(
                telegram_bot_token="123:test",
                deepseek_api_key="sk-test",
                allowed_user_ids={1},
            ),
            "conn": conn,
            "llm_client": client,
        }


class FakeLLM:
    """Scripted chat responses; chat_json_async feeds extraction."""

    def __init__(self):
        self.last_model_used = "fake-model"
        self.json_script = []
        self.chat_script = []
        self.json_calls = 0
        self.chat_calls = 0

    def queue_json(self, payload):
        self.json_script.append(payload)

    def queue_chat(self, text):
        self.chat_script.append(text)

    async def chat_json_async(self, messages, **kwargs):
        self.json_calls += 1
        item = self.json_script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    async def chat_async(self, messages, **kwargs):
        self.chat_calls += 1
        item = self.chat_script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _make_env(monkeypatch, tmp_path):
    from retrieval import TfEmbedder

    monkeypatch.setattr(bot_module, "_get_embedder", lambda: TfEmbedder())
    # Module-level debouncer carries state across tests — fresh per test.
    monkeypatch.setattr(bot_module, "DEBOUNCER", bot_module.Debouncer())
    conn = init_db(":memory:")
    client = FakeLLM()
    return conn, client


@pytest.mark.asyncio
async def test_handle_text_routine_log(monkeypatch) -> None:
    """'easy 5k done' → prelude sent, edited into the answer, logged in the
    background. Exercises the full handler — no NameError class of bugs."""
    conn, client = _make_env(monkeypatch, None)
    # persona passes (4) + editor (1); extraction for the background log.
    client.queue_chat("draft")
    client.queue_chat("draft")
    client.queue_chat("draft")
    client.queue_chat("draft")
    client.queue_chat("Nice easy 5k! Legs feeling fresh.")
    client.queue_json({"rpe": 6, "session_type": "easy_run", "distance_km": 5.0, "completed": True})

    message = FakeMessage(text="easy 5k done, RPE 6")
    update = FakeUpdate(message)
    await bot_module.handle_text(update, FakeContext(conn, client))

    assert len(message.sent) == 1  # prelude
    assert len(message.edited) == 1  # final answer replaces it
    assert "Legs feeling fresh" in message.edited[0]

    await asyncio.sleep(0)  # let the background logging task finish
    await asyncio.sleep(0)
    row = conn.execute("SELECT * FROM daily_logs").fetchone()
    assert row is not None
    assert row["rpe"] == 6
    assert row["distance_km"] == 5.0
    assert row["verified"] == 1  # trust-me: typed distance+time


@pytest.mark.asyncio
async def test_handle_text_profile_chat(monkeypatch) -> None:
    """'my height is 175' → ack folded into the single reply."""
    conn, client = _make_env(monkeypatch, None)
    client.queue_json({"height_cm": 175.0})  # profile pass
    for _ in range(5):
        client.queue_chat("draft")
    client.queue_chat("Solid. Anything else?")
    client.queue_json({})  # background extraction finds nothing

    message = FakeMessage(text="my height is 175")
    update = FakeUpdate(message)
    await bot_module.handle_text(update, FakeContext(conn, client))

    assert len(message.edited) == 1
    assert "Got it" in message.edited[0]
    assert "height 175 cm" in message.edited[0]
    row = conn.execute("SELECT * FROM athlete_profile").fetchone()
    assert row["height_cm"] == 175.0
    assert len(message.sent) == 1  # never two messages


@pytest.mark.asyncio
async def test_handle_text_red_flag_skips_pipeline(monkeypatch) -> None:
    """Chest pain → canned response, no LLM calls at all."""
    conn, client = _make_env(monkeypatch, None)
    message = FakeMessage(text="chest pain during my run")
    await bot_module.handle_text(FakeUpdate(message), FakeContext(conn, client))
    assert message.sent and "medical" in message.sent[0].lower()
    assert client.chat_calls == 0
    assert client.json_calls == 0


@pytest.mark.asyncio
async def test_handle_text_all_models_down(monkeypatch) -> None:
    """AllModelsFailed → prelude edited into a graceful message."""
    from llm_client import AllModelsFailed

    conn, client = _make_env(monkeypatch, None)
    for _ in range(4):
        client.queue_chat(AllModelsFailed("down"))
    message = FakeMessage(text="how's my week looking")
    await bot_module.handle_text(FakeUpdate(message), FakeContext(conn, client))
    assert len(message.edited) == 1
    assert "down for a sec" in message.edited[0]
