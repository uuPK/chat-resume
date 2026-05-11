"""Typed helpers for the resume agent streaming payload contract."""

from __future__ import annotations

from typing import Any

from app.types.stream import DiffItem, ResumeStreamEvent, ResumeStreamEventType


def infer_event_type(event: dict[str, Any]) -> ResumeStreamEventType:
    """Return the canonical event type for a legacy-compatible payload."""
    if event.get("tool_pending"):
        return "tool_pending"
    if event.get("tool_call_started"):
        return "tool_call"
    if event.get("tool_confirmed"):
        return "tool_confirmed"
    if event.get("tool_rejected"):
        return "tool_rejected"
    if event.get("tool_call_failed"):
        return "tool_call_failed"
    if event.get("prompt_rendered"):
        return "prompt_rendered"
    if event.get("llm_request"):
        return "llm_request"
    if event.get("llm_response"):
        return "llm_response"
    if event.get("done"):
        return "done"
    if event.get("display_message") and event.get("result") is not None:
        return "tool_result"
    if event.get("content"):
        return "text_delta"
    if event.get("session_id"):
        return "session_started"
    return "unknown"


def normalize_diff_items(value: Any) -> list[DiffItem]:
    """Coerce tool diff data into the public structured diff shape."""
    if not isinstance(value, list):
        return []
    diff_items: list[DiffItem] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        diff_item: DiffItem = {}
        for key in ("before", "after", "reason"):
            raw = item.get(key)
            if raw is not None:
                diff_item[key] = str(raw)
        if diff_item:
            diff_items.append(diff_item)
    return diff_items


def normalize_resume_stream_payload(
    event: dict[str, Any],
    *,
    resume_content: dict[str, Any] | None = None,
) -> ResumeStreamEvent:
    """Normalize runtime event dicts into the resume stream contract."""
    event_type = event.get("event_type")
    payload: ResumeStreamEvent = {
        "event_type": (
            event_type if isinstance(event_type, str) else infer_event_type(event)
        ),
        "content": str(event.get("content") or ""),
        "qr_images": (
            event.get("qr_images") if isinstance(event.get("qr_images"), list) else []
        ),
        "tool_calls": (
            event.get("tool_calls") if isinstance(event.get("tool_calls"), list) else []
        ),
        "resume_content": resume_content,
        "tool_call_started": event.get("tool_call_started"),
        "tool_pending": event.get("tool_pending"),
        "tool_confirmed": event.get("tool_confirmed"),
        "tool_rejected": event.get("tool_rejected"),
        "tool_call_failed": event.get("tool_call_failed"),
        "call_id": event.get("call_id"),
        "tool_call": event.get("tool_call"),
        "tool_id": event.get("tool_id") or _tool_id_from_event(event),
        "tool_name": event.get("tool_name"),
        "tool_display_name": event.get("tool_display_name") or event.get("tool_name"),
        "tool_input": event.get("tool_input"),
        "diff_summary": event.get("diff_summary"),
        "diff_items": normalize_diff_items(event.get("diff_items")),
        "result": event.get("result"),
        "display_message": event.get("display_message"),
        "internal_only": event.get("internal_only"),
        "prompt_rendered": event.get("prompt_rendered"),
        "llm_request": event.get("llm_request"),
        "llm_response": event.get("llm_response"),
        "agent_name": event.get("agent_name"),
        "system_prompt": event.get("system_prompt"),
        "user_message_preview": event.get("user_message_preview"),
        "model": event.get("model"),
        "messages": event.get("messages"),
        "params": event.get("params"),
        "tool_names": event.get("tool_names"),
        "response_content": event.get("response_content"),
        "latency_ms": event.get("latency_ms"),
        "tool_call_count": event.get("tool_call_count"),
        "done": bool(event.get("done", False)),
    }
    return payload


def text_delta_event(
    *,
    content: str,
    tool_calls: list[dict[str, Any]] | None = None,
    context: dict[str, Any] | None = None,
) -> ResumeStreamEvent:
    return {
        "event_type": "text_delta",
        "content": content,
        "tool_calls": tool_calls or [],
        "context": context,
        "done": False,
    }


def prompt_rendered_event(
    *,
    agent_name: str,
    system_prompt: str,
    user_message_preview: str,
) -> ResumeStreamEvent:
    return {
        "event_type": "prompt_rendered",
        "internal_only": True,
        "prompt_rendered": True,
        "agent_name": agent_name,
        "system_prompt": system_prompt,
        "user_message_preview": user_message_preview,
        "done": False,
    }


def llm_request_event(
    *,
    agent_name: str,
    model: str,
    messages: list[dict[str, Any]],
    params: dict[str, Any],
    tool_names: list[str | None],
) -> ResumeStreamEvent:
    return {
        "event_type": "llm_request",
        "internal_only": True,
        "llm_request": True,
        "agent_name": agent_name,
        "model": model,
        "messages": messages,
        "params": params,
        "tool_names": tool_names,
        "done": False,
    }


def llm_response_event(
    *,
    agent_name: str,
    model: str,
    response_content: str,
    tool_call_count: int,
    latency_ms: float,
) -> ResumeStreamEvent:
    return {
        "event_type": "llm_response",
        "internal_only": True,
        "llm_response": True,
        "agent_name": agent_name,
        "model": model,
        "response_content": response_content,
        "tool_call_count": tool_call_count,
        "latency_ms": latency_ms,
        "done": False,
    }


def tool_pending_event(
    *,
    call_id: str,
    tool_id: str,
    tool_call: dict[str, Any],
    tool_display_name: str,
    tool_input: dict[str, Any],
    diff_summary: str,
    diff_items: Any,
    tool_calls: list[dict[str, Any]],
) -> ResumeStreamEvent:
    return {
        "event_type": "tool_pending",
        "content": "",
        "tool_pending": True,
        "call_id": call_id,
        "tool_id": tool_id,
        "tool_call": tool_call,
        "tool_name": tool_display_name,
        "tool_display_name": tool_display_name,
        "tool_input": tool_input,
        "diff_summary": diff_summary,
        "diff_items": normalize_diff_items(diff_items),
        "tool_calls": tool_calls,
        "done": False,
    }


def tool_call_event(
    *,
    call_id: str,
    tool_id: str,
    tool_call: dict[str, Any],
    tool_display_name: str,
    tool_input: dict[str, Any],
    display_message: str,
    tool_calls: list[dict[str, Any]],
) -> ResumeStreamEvent:
    return {
        "event_type": "tool_call",
        "content": "",
        "tool_call_started": True,
        "call_id": call_id,
        "tool_id": tool_id,
        "tool_call": tool_call,
        "tool_name": tool_display_name,
        "tool_display_name": tool_display_name,
        "tool_input": tool_input,
        "display_message": display_message,
        "tool_calls": tool_calls,
        "done": False,
    }


def tool_rejected_event(
    *,
    call_id: str,
    tool_id: str,
    tool_display_name: str,
    diff_summary: str,
    diff_items: Any,
    result: dict[str, Any],
    tool_calls: list[dict[str, Any]],
) -> ResumeStreamEvent:
    return {
        "event_type": "tool_rejected",
        "content": "",
        "tool_rejected": True,
        "call_id": call_id,
        "tool_id": tool_id,
        "tool_name": tool_display_name,
        "tool_display_name": tool_display_name,
        "diff_summary": diff_summary,
        "diff_items": normalize_diff_items(diff_items),
        "result": result,
        "tool_calls": tool_calls,
        "done": False,
    }


def tool_call_failed_event(
    *,
    call_id: str,
    tool_id: str,
    tool_display_name: str,
    tool_calls: list[dict[str, Any]],
    result: Any,
    display_message: str | None,
) -> ResumeStreamEvent:
    return {
        "event_type": "tool_call_failed",
        "content": "",
        "tool_call_failed": True,
        "call_id": call_id,
        "tool_id": tool_id,
        "tool_name": tool_display_name,
        "tool_display_name": tool_display_name,
        "tool_calls": tool_calls,
        "result": result,
        "display_message": display_message,
        "done": False,
    }


def tool_confirmed_event(
    *,
    call_id: str,
    tool_id: str,
    tool_display_name: str,
    tool_calls: list[dict[str, Any]],
    qr_images: list[str],
    result: Any,
    display_message: str | None,
    diff_summary: str | None,
    diff_items: Any,
    context: dict[str, Any],
) -> ResumeStreamEvent:
    return {
        "event_type": "tool_confirmed",
        "content": "",
        "tool_confirmed": True,
        "call_id": call_id,
        "tool_id": tool_id,
        "tool_name": tool_display_name,
        "tool_display_name": tool_display_name,
        "tool_calls": tool_calls,
        "qr_images": qr_images,
        "result": result,
        "display_message": display_message,
        "diff_summary": diff_summary,
        "diff_items": normalize_diff_items(diff_items),
        "context": context,
        "done": False,
    }


def tool_result_event(
    *,
    call_id: str | None = None,
    tool_id: str | None = None,
    tool_display_name: str | None = None,
    tool_calls: list[dict[str, Any]],
    result: Any,
    display_message: str | None,
    context: dict[str, Any],
) -> ResumeStreamEvent:
    return {
        "event_type": "tool_result",
        "content": "",
        "call_id": call_id,
        "tool_id": tool_id,
        "tool_name": tool_display_name,
        "tool_display_name": tool_display_name,
        "tool_calls": tool_calls,
        "result": result,
        "display_message": display_message,
        "context": context,
        "done": False,
    }


def _tool_id_from_event(event: dict[str, Any]) -> str | None:
    tool_call = event.get("tool_call")
    if not isinstance(tool_call, dict):
        return None
    function = tool_call.get("function")
    if not isinstance(function, dict):
        return None
    name = function.get("name")
    return name if isinstance(name, str) and name else None


__all__ = [
    "infer_event_type",
    "llm_request_event",
    "llm_response_event",
    "normalize_diff_items",
    "normalize_resume_stream_payload",
    "prompt_rendered_event",
    "text_delta_event",
    "tool_call_event",
    "tool_call_failed_event",
    "tool_confirmed_event",
    "tool_pending_event",
    "tool_rejected_event",
    "tool_result_event",
]
