"""用于编排简历 Agent 流式会话和恢复流程。"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.agents.resume.agent import ResumeAgent
from app.infra.request_context import log_context
from app.runtime.permissions import confirmation_manager
from app.services.agent.resume_agent_session_coordinator import (
    ResumeAgentSessionCoordinator,
    ResumeAgentStreamInput,
)
from app.types.stream import (
    ResumeStreamEvent,
    session_started_event,
    stream_done_event,
    stream_error_event,
)

logger = logging.getLogger(__name__)


class ResumeAgentStreamService:
    """用于把 HTTP 之外的简历 Agent 会话规则集中在应用层。"""

    def __init__(self, db: Session):
        """用于初始化流式会话编排所需依赖。"""
        self.db = db

    async def stream_events(
        self,
        request: ResumeAgentStreamInput,
    ) -> AsyncIterator[ResumeStreamEvent]:
        """用于驱动一次完整的简历 Agent SSE 事件流。"""
        session_id = uuid4().hex
        confirmation_queue = confirmation_manager.create(session_id)

        with log_context(request_id=request.request_id, session_id=session_id):
            latest_resume_content: dict[str, Any] | None = None

            try:
                coordinator = ResumeAgentSessionCoordinator(self.db)
                session = coordinator.prepare_stream_session(
                    request=request,
                    session_id=session_id,
                )
                yield coordinator.record_public_event(
                    store=session.store,
                    session_id=session_id,
                    event=session_started_event(session_id),
                )
                event_stream = session.harness.run_resume_stream(
                    session_id=session_id,
                    agent=ResumeAgent(),
                    user_message=request.message,
                    resume_content=session.resume_content,
                    conversation_history=session.conversation_history,
                    confirmation_queue=confirmation_queue,
                    allowed_sections=session.allowed_sections,
                    event_callback=None,
                    user_id=request.user_id,
                )
                async for event in event_stream:
                    if event.get("internal_only"):
                        continue
                    resume_content = event.get("resume_content")
                    if isinstance(resume_content, dict):
                        latest_resume_content = resume_content
                    yield coordinator.record_public_event(
                        store=session.store,
                        session_id=session_id,
                        event=event,
                    )

                coordinator.persist_resume_if_changed(
                    session.resume_service,
                    resume_id=request.resume_id,
                    latest_resume_content=latest_resume_content,
                    original_resume=session.original_resume,
                )
                logger.debug("Resume agent stream completed")
                yield coordinator.record_public_event(
                    store=session.store,
                    session_id=session_id,
                    event=stream_done_event(
                        resume_content=latest_resume_content,
                    ),
                )
            except HTTPException as exc:
                yield stream_error_event(str(exc.detail))
            except Exception as exc:
                logger.exception("Resume agent stream failed")
                yield stream_error_event(f"AI服务暂时不可用: {exc}")
            finally:
                confirmation_manager.remove(session_id)

    def resume_session(self, *, session_id: str, user_id: int) -> dict[str, Any]:
        """用于恢复因工具确认中断而暂停的简历 Agent session。"""
        result = ResumeAgentSessionCoordinator(self.db).resume_paused_session(
            session_id=session_id,
            user_id=user_id,
        )
        logger.info("Resume agent session resumed applied=%s", bool(result.get("applied")))
        return result

    def replay_stream_events(
        self,
        *,
        session_id: str,
        user_id: int,
        after_sequence: int,
    ) -> list[ResumeStreamEvent]:
        """用于按 SSE cursor 回放指定 session 的公开流事件。"""
        return ResumeAgentSessionCoordinator(self.db).replay_public_events(
            session_id=session_id,
            user_id=user_id,
            after_sequence=after_sequence,
        )

    @staticmethod
    def ensure_stream_supported(request: ResumeAgentStreamInput) -> None:
        """用于兼容旧字段并拒绝已迁移的面试入口。"""
        ResumeAgentSessionCoordinator.ensure_stream_supported(request)

__all__ = ["ResumeAgentStreamInput", "ResumeAgentStreamService"]
