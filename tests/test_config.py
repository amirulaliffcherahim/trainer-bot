"""config.py tests — fail-fast validation of required env vars."""

import pytest

from config import ConfigError, load_settings

VALID_ENV = {
    "TELEGRAM_BOT_TOKEN": "123:testtoken",
    "DEEPSEEK_API_KEY": "sk-test-key",
    "ALLOWED_USER_IDS": "123456789, 42",
    "PRIMARY_MODEL": "deepseek-v4-flash",
}


def test_loads_valid_env() -> None:
    s = load_settings(VALID_ENV)
    assert s.telegram_bot_token == "123:testtoken"
    assert s.allowed_user_ids == {123456789, 42}
    assert s.primary_model == "deepseek-v4-flash"
    assert s.fallback_model == "deepseek-v4-pro"
    assert s.deepseek_base_url == "https://api.deepseek.com"


def test_missing_vars_fail_fast(monkeypatch) -> None:
    # Hermetic: the host may have .env loaded into the environment (a real
    # deploy box always will) — remove the vars so the failure path is real.
    for name in ("TELEGRAM_BOT_TOKEN", "DEEPSEEK_API_KEY", "ALLOWED_USER_IDS"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ConfigError) as exc:
        load_settings({})
    msg = str(exc.value)
    assert "TELEGRAM_BOT_TOKEN" in msg
    assert "DEEPSEEK_API_KEY" in msg
    assert "ALLOWED_USER_IDS" in msg
    assert ".env.example" in msg


def test_invalid_user_id_rejected() -> None:
    with pytest.raises(ConfigError):
        load_settings({**VALID_ENV, "ALLOWED_USER_IDS": "abc"})


def test_empty_user_ids_rejected() -> None:
    with pytest.raises(ConfigError):
        load_settings({**VALID_ENV, "ALLOWED_USER_IDS": ""})


def test_vision_key_optional() -> None:
    s = load_settings({**VALID_ENV, "VISION_API_KEY": "vision-key"})
    assert s.vision_api_key == "vision-key"
    s2 = load_settings(VALID_ENV)
    assert s2.vision_api_key is None
