"""用于把流式 Agent 执行和持久化会话编排到一起。"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator

from sqlalchemy.orm import Session

from app.agents.resume.agent import ResumeAgent
from app.runtime.recovery import recover_resume_session
from app.state.store import AgentSessionStore

logger = logging.getLogger(__name__)


class AgentHarness:
    """用于管理简历 Agent 的 session 生命周期和事件落库。"""

    def __init__(
        self,
        db: Session,
        session_store: AgentSessionStore | None = None,
    ):
        """用于初始化持久化编排层依赖。"""
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
        """用于创建一次新的简历优化 session 并记录首条用户消息。"""
        logger.debug(
            "AgentHarness create_resume_session resume_id=%s user_id=%s",
            resume_id,
            user_id,
        )
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
        event_callback=None,
        user_id: int | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """用于驱动简历 Agent 流式运行并同步写入会话事件。"""
        final_content_parts: list[str] = []
        latest_resume_content: dict[str, Any] | None = None
        logger.debug("AgentHarness run_resume_stream started")

        try:
            async for event in agent.optimize_stream(
                user_message=user_message,
                resume_content=resume_content,
                conversation_history=conversation_history,
                confirmation_queue=confirmation_queue,
                allowed_sections=allowed_sections,
                event_callback=event_callback,
                user_id=user_id,
            ):
                latest_resume_content = self._record_resume_stream_event(
                    session_id=session_id,
                    event=event,
                    final_content_parts=final_content_parts,
                    latest_resume_content=latest_resume_content,
                )
                yield event
        except Exception as exc:
            logger.exception("AgentHarness run_resume_stream failed")
            self.record_failure(session_id, exc)
            raise

        self.complete_resume_session(
            session_id=session_id,
            final_content="".join(final_content_parts),
            latest_resume_content=latest_resume_content,
        )
        logger.debug("AgentHarness run_resume_stream completed")

    def record_failure(self, session_id: str, exc: Exception) -> None:
        """用于在流式执行失败时更新会话状态并记录失败事件。"""
        if not self.session_store.get_session(session_id):
            return
        logger.error("AgentHarness record_failure error=%s", exc)
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
        """用于在流式执行结束后补齐最终回复和完成事件。"""
        logger.debug(
            "AgentHarness complete_resume_session has_checkpoint=%s",
            latest_resume_content is not None,
        )
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
        """用于把恢复请求转交给恢复模块执行。"""
        return recover_resume_session(
            session_store=self.session_store,
            session_id=session_id,
            resume_content=resume_content,
            allowed_sections=allowed_sections,
        )

    def _record_resume_stream_event(
        self,
        *,
        session_id: str,
        event: dict[str, Any],
        final_content_parts: list[str],
        latest_resume_content: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        """用于把 runtime 事件映射成 session 状态和事件日志。"""
        content = event.get("content")
        if content:
            final_content_parts.append(content)

        resume_content = event.get("resume_content")
        if isinstance(resume_content, dict):
            latest_resume_content = resume_content

        if event.get("tool_pending"):
            self.session_store.update_status(
                session_id,
                "waiting_confirmation",
                current_step=event.get("call_id"),
            )
            self.session_store.append_event(
                session_id=session_id,
                event_type="tool_call_previewed",
                source="resume_agent",
                payload={
                    "call_id": event.get("call_id"),
                    "tool_id": event.get("tool_id"),
                    "tool_name": event.get("tool_name"),
                    "tool_display_name": event.get("tool_display_name"),
                    "tool_input": event.get("tool_input"),
                    "tool_call": event.get("tool_call"),
                    "diff_summary": event.get("diff_summary"),
                    "diff_items": event.get("diff_items"),
                },
            )
            return latest_resume_content

        if event.get("tool_confirmed") or event.get("tool_rejected"):
            confirmed = bool(event.get("tool_confirmed"))
            self.session_store.append_confirmation_event(
                session_id=session_id,
                call_id=event.get("call_id") or "",
                confirmed=confirmed,
                tool_name=event.get("tool_name"),
            )
            if confirmed:
                self.session_store.update_status(session_id, "running")
            return latest_resume_content

        if event.get("tool_call_failed"):
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

        if event.get("display_message") and event.get("result") is not None:
            self.session_store.append_event(
                session_id=session_id,
                event_type="tool_call_finished",
                source="resume_agent",
                payload={
                    "call_id": event.get("call_id"),
                    "tool_name": event.get("tool_name"),
                    "result": event.get("result"),
                    "display_message": event.get("display_message"),
                },
            )

        return latest_resume_content


__all__ = ["AgentHarness"]
