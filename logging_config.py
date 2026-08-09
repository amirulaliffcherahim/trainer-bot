"""Logging setup with log rotation and secret redaction.

Security: API keys and tokens must never reach logs. RedactingFilter masks
configured secret values (from SECRET_ENV_NAMES) plus Bearer tokens in every
record before it is written.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import re
from pathlib import Path

from config import SECRET_ENV_NAMES

_BEARER_RE = re.compile(r"(Authorization:\s*Bearer|Bearer)\s+[A-Za-z0-9._\-]+")


def _secret_values() -> list[str]:
    return [os.environ.get(name, "") for name in SECRET_ENV_NAMES if os.environ.get(name)]


class RedactingFilter(logging.Filter):
    """Masks known secrets and Bearer tokens in log records."""

    def __init__(self, secrets: list[str] | None = None) -> None:
        super().__init__()
        self.secrets = [s for s in (secrets if secrets is not None else _secret_values()) if s]

    def filter(self, record: logging.LogRecord) -> bool:
        original = record.getMessage()
        msg = original
        for secret in self.secrets:
            # Guard: empty or very short values would over-match common text.
            if len(secret) > 3 and secret in msg:
                msg = msg.replace(secret, "***")
        msg = _BEARER_RE.sub(r"\1 ***", msg)
        if msg != original:
            record.msg = msg
            record.args = ()
        return True


def setup_logging(level: str = "INFO", log_dir: str = "logs") -> logging.Logger:
    """Configure root logger: console + rotating file, both redacted."""
    root = logging.getLogger()
    root.setLevel(level.upper())
    if not root.handlers:
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

        console = logging.StreamHandler()
        console.setFormatter(formatter)
        console.addFilter(RedactingFilter())
        root.addHandler(console)

        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_path / "trainer.log",
            maxBytes=1_000_000,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(RedactingFilter())
        root.addHandler(file_handler)
    return root
