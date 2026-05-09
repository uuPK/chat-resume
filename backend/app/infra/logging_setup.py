"""
Logging configuration helpers.
"""

from __future__ import annotations

import json
import logging
import re
import sys
import traceback
from datetime import datetime, timezone
from typing import Any

from loguru import logger as loguru_logger

from app.infra.config import settings
from app.infra.request_context import get_log_context

_SENSITIVE_KEYS = re.compile(
    r"(authorization|access[_-]?key|api[_-]?key|token|secret|password|cookie)",
    re.IGNORECASE,
)
_STANDARD_LOG_RECORD_KEYS = set(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__
)
_NOISY_LOGGERS = (
    "httpcore",
    "httpx",
    "openai",
    "langchain",
    "langgraph",
    "langsmith",
    "deepagents",
    "multipart",
    "passlib",
    "urllib3",
    "websockets",
)
_INTERCEPTED_LOGGERS = (
    "",
    "uvicorn",
    "uvicorn.error",
    "uvicorn.access",
)


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: (
                "[REDACTED]" if _SENSITIVE_KEYS.search(str(key)) else _sanitize(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_sanitize(item) for item in value[:20]]
    if isinstance(value, str):
        return value if len(value) <= 500 else f"{value[:500]}..."
    return value


def _context_defaults() -> dict[str, str]:
    context = get_log_context()
    return {
        "request_id": context["request_id"] or "-",
        "session_id": context["session_id"] or "-",
        "tool_call_id": context["tool_call_id"] or "-",
    }


class JsonFormatter(logging.Formatter):
    def _sanitize(self, value: Any) -> Any:
        return _sanitize(value)

    def format(self, record: logging.LogRecord) -> str:
        context = _context_defaults()
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": self._sanitize(record.getMessage()),
            "request_id": getattr(record, "request_id", context["request_id"]),
            "session_id": getattr(record, "session_id", context["session_id"]),
            "tool_call_id": getattr(
                record,
                "tool_call_id",
                context["tool_call_id"],
            ),
        }
        for key, value in record.__dict__.items():
            if (
                key.startswith("_")
                or key in payload
                or key in _STANDARD_LOG_RECORD_KEYS
            ):
                continue
            payload[key] = (
                "[REDACTED]"
                if _SENSITIVE_KEYS.search(str(key))
                else self._sanitize(value)
            )
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class InterceptHandler(logging.Handler):
    """Forward standard-library logging records into Loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = loguru_logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        depth = 2
        frame = logging.currentframe()
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        extra = {
            key: value
            for key, value in record.__dict__.items()
            if not key.startswith("_") and key not in _STANDARD_LOG_RECORD_KEYS
        }
        extra["logger_name"] = record.name
        for key, value in _context_defaults().items():
            extra.setdefault(key, value)

        loguru_logger.bind(**extra).opt(
            depth=depth,
            exception=record.exc_info,
        ).log(level, record.getMessage())


def _patch_loguru_record(record: Any) -> None:
    record["extra"].setdefault("logger_name", record["name"])
    for key, value in _context_defaults().items():
        record["extra"].setdefault(key, value)


def _json_sink(message: Any) -> None:
    record = message.record
    extra = record["extra"]
    payload: dict[str, Any] = {
        "timestamp": record["time"].astimezone(timezone.utc).isoformat(),
        "level": record["level"].name,
        "logger": extra.get("logger_name", record["name"]),
        "message": _sanitize(record["message"]),
        "request_id": extra.get("request_id", "-"),
        "session_id": extra.get("session_id", "-"),
        "tool_call_id": extra.get("tool_call_id", "-"),
    }
    for key, value in extra.items():
        if key in payload or key.startswith("_"):
            continue
        payload[key] = "[REDACTED]" if _SENSITIVE_KEYS.search(str(key)) else _sanitize(
            value
        )

    exception = record["exception"]
    if exception:
        payload["exception"] = "".join(
            traceback.format_exception(
                exception.type,
                exception.value,
                exception.traceback,
            )
        )

    sys.stderr.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stderr.flush()


def configure_logging() -> None:
    log_level_name = settings.LOG_LEVEL.upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    loguru_logger.remove()
    loguru_logger.configure(patcher=_patch_loguru_record)
    if settings.LOG_FORMAT.strip().lower() == "json":
        loguru_logger.add(
            _json_sink,
            level=log_level_name,
            backtrace=False,
            diagnose=False,
        )
    else:
        loguru_logger.add(
            sys.stderr,
            level=log_level_name,
            format=(
                "{time:YYYY-MM-DD HH:mm:ss} - {extra[logger_name]} - {level} - "
                "[req={extra[request_id]} ses={extra[session_id]} "
                "tool={extra[tool_call_id]}] {message}{exception}"
            ),
            backtrace=False,
            diagnose=False,
            colorize=False,
        )

    intercept_handler = InterceptHandler()
    for logger_name in _INTERCEPTED_LOGGERS:
        intercepted_logger = logging.getLogger(logger_name)
        intercepted_logger.handlers.clear()
        intercepted_logger.setLevel(log_level)
        intercepted_logger.addHandler(intercept_handler)
        intercepted_logger.propagate = False

    for logger_name in _NOISY_LOGGERS:
        library_logger = logging.getLogger(logger_name)
        library_logger.handlers.clear()
        library_logger.setLevel(logging.WARNING)
        library_logger.propagate = True
