"""Application settings — loaded from .env, fail-fast on missing required vars.

Security: secret values are tracked in SECRET_ENV_NAMES so the logging layer
can redact them. Never log a Settings object directly.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from pydantic import BaseModel, field_validator

load_dotenv()

REQUIRED_ENV_VARS = ("TELEGRAM_BOT_TOKEN", "DEEPSEEK_API_KEY", "ALLOWED_USER_IDS")
SECRET_ENV_NAMES = ("TELEGRAM_BOT_TOKEN", "DEEPSEEK_API_KEY", "VISION_API_KEY")


class ConfigError(RuntimeError):
    """Raised when the environment configuration is invalid."""


class Settings(BaseModel):
    telegram_bot_token: str
    deepseek_api_key: str
    deepseek_base_url: str = "https://api.deepseek.com"
    vision_api_key: str | None = None
    allowed_user_ids: set[int]
    primary_model: str = "deepseek-v4-flash"
    fallback_model: str = "deepseek-v4-pro"
    log_level: str = "INFO"
    db_path: str = "trainer_data.db"
    run_remind_time: str = "17:30"

    @field_validator("allowed_user_ids", mode="before")
    @classmethod
    def _parse_user_ids(cls, raw: object) -> object:
        if isinstance(raw, (set, frozenset)):
            return raw
        ids: set[int] = set()
        for part in str(raw).split(","):
            part = part.strip()
            if not part:
                continue
            try:
                ids.add(int(part))
            except ValueError as exc:
                raise ValueError(
                    f"ALLOWED_USER_IDS contains non-numeric id: {part!r}"
                ) from exc
        if not ids:
            raise ValueError("ALLOWED_USER_IDS must contain at least one numeric user id")
        return ids


def load_settings(env: dict[str, str] | None = None) -> Settings:
    """Build Settings from the process environment (optionally overridden).

    Raises ConfigError with a clear message listing missing required vars.
    """
    merged = dict(os.environ)
    if env:
        merged.update(env)

    missing = [name for name in REQUIRED_ENV_VARS if not merged.get(name)]
    if missing:
        raise ConfigError(
            "Missing required environment variables: "
            + ", ".join(missing)
            + ". Copy .env.example to .env and fill them in."
        )

    try:
        return Settings(
            telegram_bot_token=merged["TELEGRAM_BOT_TOKEN"],
            deepseek_api_key=merged["DEEPSEEK_API_KEY"],
            deepseek_base_url=merged.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            vision_api_key=merged.get("VISION_API_KEY") or None,
            allowed_user_ids=merged["ALLOWED_USER_IDS"],
            primary_model=merged.get("PRIMARY_MODEL", "deepseek-v4-flash"),
            fallback_model=merged.get("FALLBACK_MODEL", "deepseek-v4-pro"),
            log_level=merged.get("LOG_LEVEL", "INFO"),
            db_path=merged.get("DB_PATH", "trainer_data.db"),
            run_remind_time=merged.get("RUN_REMIND_TIME", "17:30"),
        )
    except ValueError as exc:
        raise ConfigError(f"Invalid configuration: {exc}") from exc


def get_settings() -> Settings:
    return load_settings()
