"""用于维护请求、会话和工具调用的日志上下文。"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Iterator

_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
_session_id_var: ContextVar[str | None] = ContextVar("session_id", default=None)
_tool_call_id_var: ContextVar[str | None] = ContextVar("tool_call_id", default=None)
_client_request_id_var: ContextVar[str | None] = ContextVar(
    "client_request_id", default=None
)


def get_log_context() -> dict[str, str | None]:
    """用于获取日志上下文。"""
    return {
        "request_id": _request_id_var.get(),
        "session_id": _session_id_var.get(),
        "tool_call_id": _tool_call_id_var.get(),
        "client_request_id": _client_request_id_var.get(),
    }


def bind_log_context(
    *,
    request_id: str | None = None,
    session_id: str | None = None,
    tool_call_id: str | None = None,
    client_request_id: str | None = None,
) -> dict[str, Token[str | None]]:
    """用于绑定日志上下文。"""
    tokens: dict[str, Token[str | None]] = {}
    if request_id is not None:
        tokens["request_id"] = _request_id_var.set(request_id)
    if session_id is not None:
        tokens["session_id"] = _session_id_var.set(session_id)
    if tool_call_id is not None:
        tokens["tool_call_id"] = _tool_call_id_var.set(tool_call_id)
    if client_request_id is not None:
        tokens["client_request_id"] = _client_request_id_var.set(client_request_id)
    return tokens


def reset_log_context(tokens: dict[str, Token[str | None]]) -> None:
    """用于处理reset日志上下文。"""
    if "tool_call_id" in tokens:
        _tool_call_id_var.reset(tokens["tool_call_id"])
    if "session_id" in tokens:
        _session_id_var.reset(tokens["session_id"])
    if "request_id" in tokens:
        _request_id_var.reset(tokens["request_id"])
    if "client_request_id" in tokens:
        _client_request_id_var.reset(tokens["client_request_id"])


@contextmanager
def log_context(
    *,
    request_id: str | None = None,
    session_id: str | None = None,
    tool_call_id: str | None = None,
    client_request_id: str | None = None,
) -> Iterator[None]:
    """用于处理日志上下文。"""
    tokens = bind_log_context(
        request_id=request_id,
        session_id=session_id,
        tool_call_id=tool_call_id,
        client_request_id=client_request_id,
    )
    try:
        yield
    finally:
        reset_log_context(tokens)
