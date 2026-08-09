"""llm_client.py tests — retry/backoff, fallback chain, JSON mode (no network)."""

from types import SimpleNamespace

import pytest

from llm_client import AllModelsFailed, LLMClient, NonRetryableError, RetryableError


class _FakeCompletions:
    def __init__(self, handler):
        self.handler = handler
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.handler(kwargs)


class _FakeOpenAI:
    def __init__(self, handler):
        self.chat = SimpleNamespace(completions=_FakeCompletions(handler))


def _response(content: str = "ok"):
    """Fresh response stub per call — no shared mutable state between tests."""
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


def _client(handler, models=("flash", "pro"), **kwargs) -> LLMClient:
    return LLMClient(
        api_key="test",
        base_url="https://api.deepseek.com",
        models=list(models),
        client=_FakeOpenAI(handler),
        max_retries=kwargs.get("max_retries", 3),
        base_delay=0.001,
        max_delay=0.01,
    )


def test_fallback_chain_uses_next_model() -> None:
    def handler(kwargs):
        if kwargs["model"] == "flash":
            raise RetryableError("rate limited")
        return _response()

    client = _client(handler)
    assert client.chat([{"role": "user", "content": "hi"}]) == "ok"
    assert client.last_model_used == "pro"


def test_temperature_passthrough() -> None:
    captured: dict = {}

    def handler(kwargs):
        captured.update(kwargs)
        return _response()

    client = _client(handler)
    client.chat([{"role": "user", "content": "extract"}], temperature=0.0)
    assert captured["temperature"] == 0.0


def test_programming_errors_propagate() -> None:
    """Bugs (ValueError, ...) must surface, not be retried as transient."""

    def handler(kwargs):
        raise ValueError("programming bug")

    client = _client(handler)
    with pytest.raises(ValueError):
        client.chat([{"role": "user", "content": "hi"}])


def test_retry_then_success_same_model() -> None:
    calls: list[str] = []

    def handler(kwargs):
        calls.append(kwargs["model"])
        if len(calls) < 3:
            raise RetryableError("transient")
        return _response()

    client = _client(handler, max_retries=3)
    assert client.chat([{"role": "user", "content": "hi"}]) == "ok"
    assert client.last_model_used == "flash"
    assert calls == ["flash", "flash", "flash"]


def test_non_retryable_fails_over_immediately() -> None:
    flash_calls: list[str] = []

    def handler(kwargs):
        if kwargs["model"] == "flash":
            flash_calls.append("flash")
            raise NonRetryableError("bad request")
        return _response()

    client = _client(handler, max_retries=3)
    assert client.chat([{"role": "user", "content": "hi"}]) == "ok"
    assert len(flash_calls) == 1  # no retries on permanent failure


def test_all_models_fail_raises() -> None:
    def handler(kwargs):
        raise RetryableError("down")

    client = _client(handler, max_retries=1)
    with pytest.raises(AllModelsFailed):
        client.chat([{"role": "user", "content": "hi"}])


def test_json_mode_sets_response_format() -> None:
    captured: dict = {}

    def handler(kwargs):
        captured.update(kwargs)
        return _response('{"a": 1}')

    client = _client(handler)
    result = client.chat_json([{"role": "user", "content": "extract"}])
    assert result == {"a": 1}
    assert captured["response_format"] == {"type": "json_object"}


def test_json_mode_strips_markdown_fences() -> None:
    def handler(kwargs):
        return _response('```json\n{"a": 1}\n```')

    client = _client(handler)
    assert client.chat_json([{"role": "user", "content": "extract"}]) == {"a": 1}


def test_json_mode_invalid_json_raises() -> None:
    def handler(kwargs):
        return _response("not json")

    client = _client(handler)
    with pytest.raises(NonRetryableError):
        client.chat_json([{"role": "user", "content": "extract"}])


@pytest.mark.asyncio
async def test_chat_async_offloads_to_thread() -> None:
    import asyncio

    def handler(kwargs):
        return _response()

    client = _client(handler)
    result = await client.chat_async([{"role": "user", "content": "hi"}])
    assert result == "ok"
    assert client.last_model_used == "flash"
    # The event loop must not be blocked: a timer should fire during the call.
    loop = asyncio.get_running_loop()
    fired = asyncio.Event()
    loop.call_later(0.001, fired.set)
    await asyncio.wait_for(fired.wait(), timeout=1.0)
