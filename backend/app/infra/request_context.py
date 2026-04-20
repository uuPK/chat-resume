"""
Lightweight request/session/tool correlation context for logs and events.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Iterator

_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
_session_id_var: ContextVar[str | None] = ContextVar("session_id", default=None)
_tool_call_id_var: ContextVar[str | None] = ContextVar("tool_call_id", default=None)


def get_log_context() -> dict[str, str | None]:
    return {
        "request_id": _request_id_var.get(),
        "session_id": _session_id_var.get(),
        "tool_call_id": _tool_call_id_var.get(),
    }


def bind_log_context(
    *,
    request_id: str | None = None,
    session_id: str | None = None,
    tool_call_id: str | None = None,
) -> dict[str, Token[str | None]]:
    tokens: dict[str, Token[str | None]] = {}
    if request_id is not None:
        tokens["request_id"] = _request_id_var.set(request_id)
    if session_id is not None:
        tokens["session_id"] = _session_id_var.set(session_id)
    if tool_call_id is not None:
        tokens["tool_call_id"] = _tool_call_id_var.set(tool_call_id)
    return tokens


def reset_log_context(tokens: dict[str, Token[str | None]]) -> None:
    if "tool_call_id" in tokens:
        _tool_call_id_var.reset(tokens["tool_call_id"])
    if "session_id" in tokens:
        _session_id_var.reset(tokens["session_id"])
    if "request_id" in tokens:
        _request_id_var.reset(tokens["request_id"])


@contextmanager
def log_context(
    *,
    request_id: str | None = None,
    session_id: str | None = None,
    tool_call_id: str | None = None,
) -> Iterator[None]:
    tokens = bind_log_context(
        request_id=request_id,
        session_id=session_id,
        tool_call_id=tool_call_id,
    )
    try:
        yield
    finally:
        reset_log_context(tokens)


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        context = get_log_context()
        record.request_id = context["request_id"] or "-"
        record.session_id = context["session_id"] or "-"
        record.tool_call_id = context["tool_call_id"] or "-"
        return True
