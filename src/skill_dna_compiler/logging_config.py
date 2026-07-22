from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any

_SECRET_PATTERNS = (
    re.compile(r"(?i)(OPENAI_API_KEY\s*[=:]\s*)\S+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
)


def redact_text(value: str) -> str:
    redacted = value
    redacted = _SECRET_PATTERNS[0].sub(r"\1[REDACTED]", redacted)
    redacted = _SECRET_PATTERNS[1].sub("[REDACTED]", redacted)
    return redacted


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, tuple):
        return tuple(_redact_value(item) for item in value)
    if isinstance(value, Mapping):
        return {key: _redact_value(item) for key, item in value.items()}
    return value


class SensitiveDataFilter(logging.Filter):
    """Remove credential-like values before a record reaches any handler."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _redact_value(record.msg)
        record.args = _redact_value(record.args)
        return True


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.addFilter(SensitiveDataFilter())
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

