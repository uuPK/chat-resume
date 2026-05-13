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
    "langsmith",
    "multipart",
    "passlib",
    "pdfminer",
    "urllib3",
    "websockets",
)
_INTERCEPTED_LOGGERS = (
    "",
    "uvicorn",
    "uvicorn.error",
    "uvicorn.access",
)
_TRACE_VALUE_LIMIT = 48
_TRACE_KEY_LABELS = {
    "agent_name": "agent",
    "call_id": "call",
    "confirmed": "confirmed",
    "diff_item_count": "diffs",
    "diff_summary": "diff",
    "display_message": "msg",
    "latency_ms": "ms",
    "requires_confirmation": "confirm",
    "result_success": "ok",
    "result_summary": "result",
    "run_id": "run",
    "tool_display_name": "display",
    "tool_input": "input",
    "tool_name": "tool",
}


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
    extra = record["extra"]
    extra.setdefault("logger_name", record["name"])
    for key, value in _context_defaults().items():
        extra.setdefault(key, value)
    extra["logger_label"] = _logger_label(str(extra["logger_name"]))
    extra["request_id_short"] = _short_identifier(extra["request_id"])
    extra["session_id_short"] = _short_identifier(extra["session_id"])
    extra["tool_call_id_short"] = _short_identifier(extra["tool_call_id"])
    extra["message_label"] = _message_label(record["message"], extra)
    extra["agent_trace_suffix"] = _agent_trace_suffix(extra)


def _logger_label(logger_name: str) -> str:
    if logger_name == "app.runtime.pi_agent_runtime":
        return "piagent"
    if logger_name.startswith("app."):
        parts = logger_name.split(".")
        return ".".join(parts[-2:])
    return logger_name


def _short_identifier(value: Any, limit: int = 6) -> str:
    text = str(value or "-")
    if text == "-" or len(text) <= limit:
        return text
    return text[:limit]


def _message_label(message: str, extra: dict[str, Any]) -> str:
    if extra.get("agent_trace") and message.startswith("agent.trace."):
        return message.removeprefix("agent.")
    return message


def _agent_trace_suffix(extra: dict[str, Any]) -> str:
    if not extra.get("agent_trace"):
        return ""
    trace_fields = {
        key: value
        for key, value in extra.items()
        if key
        not in {
            "agent_trace",
            "agent_trace_suffix",
            "logger_name",
            "logger_label",
            "message_label",
            "request_id",
            "request_id_short",
            "session_id",
            "session_id_short",
            "tool_call_id",
            "tool_call_id_short",
        }
    }
    if not trace_fields:
        return ""
    ordered_keys = [
        "run_id",
        "agent_name",
        "mode",
        "model",
        "tool_name",
        "tool_display_name",
        "call_id",
        "confirmed",
        "requires_confirmation",
        "result_success",
        "reason",
        "chunk_index",
        "chunk_count",
        "latency_ms",
    ]
    parts: list[str] = []
    for key in ordered_keys:
        if key in trace_fields:
            parts.append(_format_trace_pair(key, trace_fields.pop(key)))
    for key in sorted(trace_fields):
        parts.append(_format_trace_pair(key, trace_fields[key]))
    return " | " + " ".join(parts)


def _format_trace_pair(key: str, value: Any) -> str:
    label = _TRACE_KEY_LABELS.get(key, key)
    return f"{label}={_format_trace_value(key, value)}"


def _format_trace_value(key: str, value: Any) -> str:
    sanitized = _compact_trace_value(_sanitize(value))
    if key.endswith("_id") and isinstance(sanitized, str):
        sanitized = _short_identifier(sanitized, limit=8)
    if isinstance(sanitized, str):
        if re.fullmatch(r"[\w.\-:/]+", sanitized):
            return sanitized
        return json.dumps(sanitized, ensure_ascii=False, default=str)
    if isinstance(sanitized, bool):
        return str(sanitized).lower()
    if isinstance(sanitized, (int, float)) or sanitized is None:
        return json.dumps(sanitized, ensure_ascii=False, default=str)
    return json.dumps(
        sanitized,
        ensure_ascii=False,
        default=str,
        sort_keys=True,
        separators=(",", ":"),
    )


def _compact_trace_value(value: Any) -> Any:
    if isinstance(value, str):
        normalized = " ".join(value.split())
        if len(normalized) <= _TRACE_VALUE_LIMIT:
            return normalized
        return f"{normalized[:_TRACE_VALUE_LIMIT]}..."
    if isinstance(value, dict):
        return {
            str(key): _compact_trace_value(item)
            for key, item in list(value.items())[:8]
        }
    if isinstance(value, list):
        return [_compact_trace_value(item) for item in value[:5]]
    return value


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
                "{time:HH:mm:ss} {level} {extra[logger_label]} "
                "{extra[message_label]}{extra[agent_trace_suffix]}"
                "{exception}"
            ),
            backtrace=False,
            diagnose=False,
            colorize=False,
        )

    intercept_handler = InterceptHandler()
    for logger_name in _INTERCEPTED_LOGGERS:
        intercepted_logger = logging.getLogger(logger_name)
        intercepted_logger.handlers.clear()
        intercepted_logger.setLevel(
            logging.WARNING if logger_name.startswith("uvicorn") else log_level
        )
        intercepted_logger.addHandler(intercept_handler)
        intercepted_logger.propagate = False

    for logger_name in _NOISY_LOGGERS:
        library_logger = logging.getLogger(logger_name)
        library_logger.handlers.clear()
        library_logger.setLevel(logging.WARNING)
        library_logger.propagate = True
