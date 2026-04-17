"""用于定义简历 Agent SSE 通道的事件载荷结构。"""

from __future__ import annotations

from typing import Any, TypedDict


class ResumeStreamEvent(TypedDict, total=False):
    """用于约束前后端流式事件字段的可选集合。"""

    content: str
    qr_images: list[str]
    tool_calls: list[dict[str, Any]]
    resume_content: dict[str, Any]
    tool_pending: bool
    tool_confirmed: bool
    tool_rejected: bool
    tool_call_failed: bool
    call_id: str
    tool_call: dict[str, Any]
    tool_name: str
    tool_input: dict[str, Any]
    diff_summary: str
    diff_items: list[dict[str, Any]]
    result: dict[str, Any]
    display_message: str
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
    tool_names: list[str]
    response_content: str
    latency_ms: float
    tool_call_count: int
    done: bool
    session_id: str
    error: str


__all__ = ["ResumeStreamEvent"]
