"""用于定义简历 Agent SSE 通道的事件载荷结构。"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

ResumeStreamEventType = Literal[
    "session_started",
    "text_delta",
    "tool_pending",
    "tool_confirmed",
    "tool_rejected",
    "tool_call_failed",
    "tool_result",
    "prompt_rendered",
    "llm_request",
    "llm_response",
    "done",
    "unknown",
]


class DiffItem(TypedDict, total=False):
    """用于描述单条结构化简历改动。"""

    before: str
    after: str
    reason: str


class ResumeStreamEvent(TypedDict, total=False):
    """用于约束前后端流式事件字段的可选集合。"""

    event_type: ResumeStreamEventType
    content: str
    qr_images: list[str]
    tool_calls: list[dict[str, Any]]
    resume_content: dict[str, Any] | None
    tool_pending: bool
    tool_confirmed: bool
    tool_rejected: bool
    tool_call_failed: bool
    call_id: str
    tool_call: dict[str, Any]
    tool_id: str
    tool_name: str
    tool_display_name: str
    tool_input: dict[str, Any]
    diff_summary: str
    diff_items: list[DiffItem]
    result: Any
    display_message: str | None
    internal_only: bool
    prompt_rendered: bool
    llm_request: bool
    llm_response: bool
    agent_name: str
    system_prompt: str
    user_message_preview: str
    model: str
    messages: list[dict[str, Any]]
    params: dict[str, Any]
    tool_names: list[str | None]
    response_content: str
    latency_ms: float
    tool_call_count: int
    context: dict[str, Any] | None
    done: bool
    session_id: str
    error: str


__all__ = ["DiffItem", "ResumeStreamEvent", "ResumeStreamEventType"]
