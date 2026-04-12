"""
Agent harness for durable stream orchestration.

The harness owns session/event recording around the existing business agents.
It deliberately reuses ResumeAgent.optimize_stream for now; later phases can
move more runtime policy into this layer without changing the API endpoint.
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator

from sqlalchemy.orm import Session

from .agent_session_store import AgentSessionStore
from .resume_agent import ResumeAgent


class AgentHarness:
    def __init__(self, db: Session, session_store: AgentSessionStore | None = None):
        self.db = db
        self.session_store = session_store or AgentSessionStore(db)

    def create_resume_session(
        self,
        *,
        session_id: str,
        user_id: int,
        resume_id: int,
        user_message: str,
        visible_modules: list[str],
    ) -> None:
        self.session_store.create_session(
            session_id=session_id,
            user_id=user_id,
            resume_id=resume_id,
            task_type="resume_optimization",
            metadata={
                "visible_modules": visible_modules,
                "agent_type": "resume",
            },
        )
        self.session_store.update_status(session_id, "running")
        self.session_store.append_event(
            session_id=session_id,
            event_type="user_message",
            source="user",
            payload={"content": user_message},
        )

    async def run_resume_stream(
        self,
        *,
        session_id: str,
        agent: ResumeAgent,
        user_message: str,
        resume_content: dict[str, Any],
        conversation_history: list[dict[str, str]],
        confirmation_queue: asyncio.Queue | None,
        allowed_sections: set[str],
    ) -> AsyncIterator[dict[str, Any]]:
        final_content_parts: list[str] = []
        latest_resume_content: dict[str, Any] | None = None

        try:
            async for event in agent.optimize_stream(
                user_message=user_message,
                resume_content=resume_content,
                conversation_history=conversation_history,
                confirmation_queue=confirmation_queue,
                allowed_sections=allowed_sections,
            ):
                latest_resume_content = self._record_resume_stream_event(
                    session_id=session_id,
                    event=event,
                    final_content_parts=final_content_parts,
                    latest_resume_content=latest_resume_content,
                )
                yield event
        except Exception as exc:
            self.record_failure(session_id, exc)
            raise

        self.complete_resume_session(
            session_id=session_id,
            final_content="".join(final_content_parts),
            latest_resume_content=latest_resume_content,
        )

    def record_failure(self, session_id: str, exc: Exception) -> None:
        if not self.session_store.get_session(session_id):
            return
        self.session_store.update_status(
            session_id,
            "failed",
            failed_reason=str(exc),
        )
        self.session_store.append_event(
            session_id=session_id,
            event_type="session_failed",
            source="system",
            payload={"error": str(exc)},
        )

    def complete_resume_session(
        self,
        *,
        session_id: str,
        final_content: str,
        latest_resume_content: dict[str, Any] | None,
    ) -> None:
        if final_content:
            self.session_store.append_event(
                session_id=session_id,
                event_type="agent_response",
                source="resume_agent",
                payload={"content": final_content},
            )
        if latest_resume_content is not None:
            self.session_store.append_event(
                session_id=session_id,
                event_type="checkpoint_saved",
                source="resume_agent",
                payload={"resume_content": latest_resume_content},
            )
        self.session_store.update_status(session_id, "completed")
        self.session_store.append_event(
            session_id=session_id,
            event_type="session_completed",
            source="system",
            payload={},
        )

    def resume_session(
        self,
        *,
        session_id: str,
        resume_content: dict[str, Any],
        allowed_sections: set[str],
    ) -> dict[str, Any]:
        session = self.session_store.get_session(session_id)
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

        pending_event = self.session_store.get_latest_event(
            session_id,
            event_type="tool_call_previewed",
        )
        confirmation_event = self.session_store.get_latest_event(session_id)
        if (
            not pending_event
            or not isinstance(pending_event.payload, dict)
            or not confirmation_event
            or confirmation_event.event_type
            not in {"tool_call_confirmed", "tool_call_rejected"}
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
            self.session_store.update_status(
                session_id,
                "completed",
                clear_current_step=True,
            )
            self.session_store.append_event(
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
        self.session_store.update_status(session_id, "running")
        tool_result = agent._run_tool(
            tool_call,
            {
                "resume_content": resume_content,
                "allowed_sections": allowed_sections,
            },
        )
        result_payload = tool_result.get("result")
        if isinstance(result_payload, dict) and result_payload.get("success") is False:
            self.session_store.append_event(
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
            self.session_store.update_status(
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

        self.session_store.append_event(
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
        self.complete_resume_session(
            session_id=session_id,
            final_content="已恢复并应用确认的简历修改。",
            latest_resume_content=resume_content,
        )
        return {
            "success": True,
            "applied": True,
            "message": "已恢复并应用确认的简历修改",
            "resume_content": resume_content,
            "tool_result": tool_result,
        }

    def _record_resume_stream_event(
        self,
        *,
        session_id: str,
        event: dict[str, Any],
        final_content_parts: list[str],
        latest_resume_content: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if event.get("resume_content") is not None:
            latest_resume_content = event["resume_content"]
        if event.get("content"):
            final_content_parts.append(event["content"])

        if event.get("tool_pending"):
            call_id = event.get("call_id")
            self.session_store.update_status(
                session_id,
                "waiting_confirmation",
                current_step=call_id or "tool_confirmation",
            )
            self.session_store.append_event(
                session_id=session_id,
                event_type="tool_call_previewed",
                source="resume_agent",
                payload={
                    "call_id": call_id,
                    "tool_call": event.get("tool_call"),
                    "tool_name": event.get("tool_name"),
                    "diff_summary": event.get("diff_summary"),
                },
            )
        elif event.get("tool_confirmed"):
            self.session_store.update_status(
                session_id,
                "running",
                clear_current_step=True,
            )
            self.session_store.append_confirmation_event(
                session_id=session_id,
                call_id=event.get("call_id") or "",
                confirmed=True,
                tool_name=event.get("tool_name"),
            )
        elif event.get("tool_rejected"):
            self.session_store.update_status(
                session_id,
                "running",
                clear_current_step=True,
            )
            self.session_store.append_confirmation_event(
                session_id=session_id,
                call_id=event.get("call_id") or "",
                confirmed=False,
                tool_name=event.get("tool_name"),
            )
        elif event.get("tool_call_failed"):
            self.session_store.append_event(
                session_id=session_id,
                event_type="tool_call_failed",
                source="resume_agent",
                payload={
                    "call_id": event.get("call_id"),
                    "tool_name": event.get("tool_name"),
                    "result": event.get("result"),
                    "display_message": event.get("display_message"),
                },
            )

        return latest_resume_content
