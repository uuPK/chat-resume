"""用于承接暂停后可恢复的简历 Agent 会话。"""

from __future__ import annotations

from typing import Any

from app.agents.resume.agent import ResumeAgent
from app.state.store import AgentSessionStore


def recover_resume_session(
    *,
    session_store: AgentSessionStore,
    session_id: str,
    resume_content: dict[str, Any],
    allowed_sections: set[str],
) -> dict[str, Any]:
    """用于根据已持久化事件恢复一次待确认的简历工具执行。"""
    session = session_store.get_session(session_id)
    if not session:
        return {
            "success": False,
            "message": f"Session {session_id} 不存在",
            "resume_content": resume_content,
        }
    if session.status != "paused":
        return {
            "success": False,
            "message": f"Session {session_id} 当前状态为 {session.status}，不能恢复",
            "resume_content": resume_content,
        }

    pending_event = session_store.get_latest_event(
        session_id,
        event_type="tool_call_previewed",
    )
    confirmation_event = session_store.get_latest_event(session_id)
    if (
        not pending_event
        or not isinstance(pending_event.payload, dict)
        or not confirmation_event
        or confirmation_event.event_type not in {"tool_call_confirmed", "tool_call_rejected"}
        or not isinstance(confirmation_event.payload, dict)
    ):
        return {
            "success": False,
            "message": "缺少可恢复的工具确认事件",
            "resume_content": resume_content,
        }

    call_id = pending_event.payload.get("call_id")
    if confirmation_event.payload.get("call_id") != call_id:
        return {
            "success": False,
            "message": "最新确认事件与待执行工具不匹配",
            "resume_content": resume_content,
        }

    if confirmation_event.event_type == "tool_call_rejected":
        session_store.update_status(
            session_id,
            "completed",
            clear_current_step=True,
        )
        session_store.append_event(
            session_id=session_id,
            event_type="session_completed",
            source="system",
            payload={"resumed": True, "applied": False},
        )
        return {
            "success": True,
            "applied": False,
            "message": "已恢复 session：用户拒绝了该工具调用，未修改简历",
            "resume_content": resume_content,
        }

    tool_call = pending_event.payload.get("tool_call")
    if not isinstance(tool_call, dict):
        return {
            "success": False,
            "message": "待恢复事件缺少原始 tool_call，无法继续执行",
            "resume_content": resume_content,
        }

    agent = ResumeAgent()
    session_store.update_status(session_id, "running")
    tool_result = agent._run_tool(
        tool_call,
        {
            "resume_content": resume_content,
            "allowed_sections": allowed_sections,
        },
    )
    result_payload = tool_result.get("result")
    if isinstance(result_payload, dict) and result_payload.get("success") is False:
        session_store.append_event(
            session_id=session_id,
            event_type="tool_call_failed",
            source="resume_agent",
            payload={
                "call_id": call_id,
                "tool_name": tool_result.get("tool_name"),
                "result": result_payload,
                "resumed": True,
            },
        )
        session_store.update_status(
            session_id,
            "failed",
            failed_reason=tool_result.get("display_message"),
        )
        return {
            "success": False,
            "message": tool_result.get("display_message") or "恢复执行失败",
            "resume_content": resume_content,
            "tool_result": tool_result,
        }

    session_store.append_event(
        session_id=session_id,
        event_type="tool_call_finished",
        source="resume_agent",
        payload={
            "call_id": call_id,
            "tool_name": tool_result.get("tool_name"),
            "result": result_payload,
            "resumed": True,
        },
    )
    session_store.append_event(
        session_id=session_id,
        event_type="checkpoint_saved",
        source="resume_agent",
        payload={"resume_content": resume_content, "resumed": True},
    )
    session_store.update_status(
        session_id,
        "completed",
        clear_current_step=True,
    )
    session_store.append_event(
        session_id=session_id,
        event_type="session_completed",
        source="system",
        payload={"resumed": True, "applied": True},
    )
    return {
        "success": True,
        "applied": True,
        "message": "已恢复 session 并完成工具执行",
        "resume_content": resume_content,
        "tool_result": tool_result,
    }


__all__ = ["recover_resume_session"]
