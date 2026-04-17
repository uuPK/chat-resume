"""用于把事件历史归约成轻量 session 快照。"""

from __future__ import annotations

from typing import Iterable

from app.types.session import (
    LatestSummary,
    PendingAction,
    ResumableStep,
    SessionSnapshot,
)
from app.state.models import AgentEvent, AgentSession


def reduce_session_snapshot(
    session: AgentSession,
    events: Iterable[AgentEvent],
) -> SessionSnapshot:
    """用于从完整事件流中提炼当前前端最关心的状态。"""
    pending_action = None
    latest_summary = None
    resumable_step = None

    for event in events:
        payload = event.payload if isinstance(event.payload, dict) else {}
        if event.event_type == "tool_call_previewed":
            pending_action = PendingAction(
                type="tool_confirmation",
                tool_name=str(payload.get("tool_name") or ""),
                call_id=str(payload.get("call_id") or ""),
                summary=str(payload.get("diff_summary") or ""),
                input=payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else None,
            )
            resumable_step = ResumableStep(
                kind="tool_execution",
                call_id=str(payload.get("call_id") or ""),
                event_sequence=event.sequence,
            )
        elif event.event_type == "agent_response":
            latest_summary = LatestSummary(text=str(payload.get("content") or ""))
        elif event.event_type in {"tool_call_confirmed", "tool_call_rejected", "session_completed"}:
            pending_action = None

    return SessionSnapshot(
        status=session.status,
        pending_action=pending_action,
        latest_summary=latest_summary,
        resumable_step=resumable_step,
    )


__all__ = ["reduce_session_snapshot"]
