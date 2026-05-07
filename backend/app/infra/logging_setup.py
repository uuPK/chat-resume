"""
Logging configuration helpers.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from app.infra.config import settings
from app.infra.request_context import RequestContextFilter


class JsonFormatter(logging.Formatter):
    _SENSITIVE_KEYS = re.compile(
        r"(authorization|access[_-]?key|api[_-]?key|token|secret|password|cookie)",
        re.IGNORECASE,
    )

    def _sanitize(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: (
                    "[REDACTED]"
                    if self._SENSITIVE_KEYS.search(str(key))
                    else self._sanitize(item)
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._sanitize(item) for item in value[:20]]
        if isinstance(value, str):
            return value if len(value) <= 500 else f"{value[:500]}..."
        return value

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": self._sanitize(record.getMessage()),
            "request_id": getattr(record, "request_id", "-"),
            "session_id": getattr(record, "session_id", "-"),
            "tool_call_id": getattr(record, "tool_call_id", "-"),
        }
        for key, value in record.__dict__.items():
            if key.startswith("_") or key in payload or key in logging.LogRecord(
                "", 0, "", 0, "", (), None
            ).__dict__:
                continue
            payload[key] = (
                "[REDACTED]"
                if self._SENSITIVE_KEYS.search(str(key))
                else self._sanitize(value)
            )
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    formatter: logging.Formatter
    if settings.LOG_FORMAT.strip().lower() == "json":
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            (
                "%(asctime)s - %(name)s - %(levelname)s - "
                "[req=%(request_id)s ses=%(session_id)s "
                "tool=%(tool_call_id)s] %(message)s"
            ),
            "%Y-%m-%d %H:%M:%S",
        )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.addFilter(RequestContextFilter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(log_level)
    root_logger.addHandler(handler)

    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("multipart").setLevel(logging.WARNING)
    logging.getLogger("passlib").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)
