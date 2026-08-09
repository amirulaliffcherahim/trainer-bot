"""LLM client — DeepSeek (OpenAI-compatible), provider-agnostic.

One interface for every LLM call in the bot. DeepSeek V4-Flash is primary;
the fallback chain tries FALLBACK_MODEL, then raises AllModelsFailed so
callers can switch to degraded deterministic mode. Retries use exponential
backoff with jitter on rate limits, server errors, and timeouts.

DeepSeek's API is text-only: image/vision calls live in a separate module
(Phase 5, strava pipeline) — never add image inputs here.
"""

from __future__ import annotations

import json
import logging
import random
import re
import time
from typing import Any

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, RateLimitError

log = logging.getLogger(__name__)


class RetryableError(Exception):
    """Transient failure (429/5xx/timeout/connection) — safe to retry or fail over."""


class NonRetryableError(Exception):
    """Permanent failure (400/401/... ) — fail over to the next model immediately."""


class AllModelsFailed(RuntimeError):
    """Every model in the fallback chain failed. Caller should use degraded mode."""


def _classify_error(exc: Exception) -> RetryableError | NonRetryableError:
    if isinstance(exc, (RateLimitError, APITimeoutError, APIConnectionError)):
        return RetryableError(str(exc))
    if isinstance(exc, APIStatusError):
        if exc.status_code >= 500:
            return RetryableError(str(exc))
        return NonRetryableError(str(exc))
    if isinstance(exc, (RetryableError, NonRetryableError)):
        return exc
    # Unknown failure: retry once, then fail over.
    return RetryableError(str(exc))


class LLMClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        models: list[str],
        client: OpenAI | None = None,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 8.0,
        timeout: float = 60.0,
    ) -> None:
        self.models = list(models)
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.last_model_used: str | None = None
        # max_retries=0: the SDK's own retry loop is disabled so *our* backoff
        # policy controls the chain.
        self._client = client or OpenAI(
            api_key=api_key, base_url=base_url, timeout=timeout, max_retries=0
        )

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        json_mode: bool = False,
        thinking: bool = False,
        reasoning_effort: str | None = None,
        temperature: float | None = None,
    ) -> str:
        failures: list[tuple[str, int, str]] = []
        for model in self.models:
            for attempt in range(self.max_retries + 1):
                try:
                    content = self._call_model(
                        model,
                        messages,
                        json_mode=json_mode,
                        thinking=thinking,
                        reasoning_effort=reasoning_effort,
                        temperature=temperature,
                    )
                    self.last_model_used = model
                    return content
                except NonRetryableError as exc:
                    log.warning("LLM %s failed permanently: %s", model, exc)
                    failures.append((model, attempt, str(exc)))
                    break  # next model
                except RetryableError as exc:
                    failures.append((model, attempt, str(exc)))
                    if attempt < self.max_retries:
                        self._backoff(attempt)
                        continue
                    log.warning("LLM %s exhausted retries: %s", model, exc)
                    break  # next model
        raise AllModelsFailed(f"All models failed: {failures}")

    async def chat_async(
        self,
        messages: list[dict[str, str]],
        **kwargs,
    ) -> str:
        """Async variant — runs the blocking call off the event loop.

        python-telegram-bot handlers are async; never block the loop with
        the sync chat(). Phase 3/4 run the 4 persona passes concurrently
        with asyncio.gather on this method.
        """
        import asyncio

        return await asyncio.to_thread(self.chat, messages, **kwargs)

    async def chat_json_async(
        self,
        messages: list[dict[str, str]],
        **kwargs,
    ) -> dict[str, Any]:
        import asyncio

        return await asyncio.to_thread(self.chat_json, messages, **kwargs)

    def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        thinking: bool = False,
        reasoning_effort: str | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """Chat in JSON-output mode and parse the response.

        Defensively strips markdown code fences (```json ... ```) — models
        sometimes wrap JSON in fences even in json mode. Raises
        NonRetryableError if the model returns unparseable content.
        """
        content = self.chat(
            messages,
            json_mode=True,
            thinking=thinking,
            reasoning_effort=reasoning_effort,
            temperature=temperature,
        )
        cleaned = re.sub(r"^```(?:json)?\s*", "", content.strip())
        cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise NonRetryableError(
                f"Model returned non-JSON in json mode: {content[:200]!r}"
            ) from exc
        if not isinstance(parsed, dict):
            raise NonRetryableError(f"JSON output is not an object: {content[:200]!r}")
        return parsed

    def _call_model(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        json_mode: bool,
        thinking: bool,
        reasoning_effort: str | None,
        temperature: float | None,
    ) -> str:
        kwargs: dict[str, Any] = {"model": model, "messages": messages}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort
        if temperature is not None:
            kwargs["temperature"] = temperature
        extra_body: dict[str, Any] = {}
        if thinking:
            extra_body["thinking"] = {"type": "enabled"}
        if extra_body:
            kwargs["extra_body"] = extra_body
        try:
            response = self._client.chat.completions.create(**kwargs)
        except (
            RateLimitError,
            APITimeoutError,
            APIConnectionError,
            APIStatusError,
        ) as exc:
            # Only SDK errors we understand get classified. Anything else
            # (ValueError, TypeError, ...) is a programming bug and must
            # surface, not be silently retried.
            raise _classify_error(exc)
        content = response.choices[0].message.content
        if content is None:
            raise RetryableError("Empty completion content")
        return content

    def _backoff(self, attempt: int) -> None:
        delay = min(self.max_delay, self.base_delay * (2**attempt)) + random.uniform(0, 0.5)
        time.sleep(delay)
