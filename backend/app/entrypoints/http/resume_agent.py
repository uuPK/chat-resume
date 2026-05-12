"""
智能聊天API端点模块

提供与 AI Agent 聊天交互的 API 端点，包括简历优化。
"""

import json
import logging
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.entrypoints.http.deps import get_current_user
from app.infra.database import get_db
from app.infra.request_context import log_context
from app.runtime.permissions import confirmation_manager
from app.services.agent import (
    ResumeAgentConfirmationConflict,
    ResumeAgentSessionNotFound,
    ResumeAgentSessionService,
    ResumeAgentStreamInput,
    ResumeAgentStreamService,
)
from app.services.llm import ChatService
from app.state import AgentSessionStore
from app.types.stream import public_resume_stream_event

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatRequest(BaseModel):
    """用于承载简历 Agent 聊天请求体。"""

    message: str
    resume_id: int
    chat_history: list = []  # 聊天历史，可选
    visible_modules: list[str] = []
    agent_type: str = "resume"
    is_interview: bool = False  # 兼容旧前端字段；面试主链路已迁移到 /api/interviews


class ConfirmToolRequest(BaseModel):
    """用于承载工具确认结果。"""

    session_id: str
    call_id: str
    confirmed: bool


class ResumeSessionRequest(BaseModel):
    """用于承载暂停 session 的恢复请求。"""

    session_id: str


@router.post("/chat/stream")
async def chat_with_resume_stream(
    request: Request,
    chat_request: ChatRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于以 SSE 方式驱动一次完整的简历 Agent 流式对话。"""
    stream_input = ResumeAgentStreamInput(
        message=chat_request.message,
        resume_id=chat_request.resume_id,
        user_id=current_user["id"],
        request_id=getattr(request.state, "request_id", None),
        chat_history=cast(list[dict[str, str]], chat_request.chat_history),
        visible_modules=chat_request.visible_modules,
        agent_type=chat_request.agent_type,
        is_interview=chat_request.is_interview,
    )
    ResumeAgentStreamService.ensure_stream_supported(stream_input)
    logger.debug(
        "resume_agent.stream.requested",
        extra={
            "agent_type": stream_input.agent_type,
            "resume_id": chat_request.resume_id,
            "user_id": current_user["id"],
            "message_chars": len(chat_request.message or ""),
        },
    )
    stream_service = ResumeAgentStreamService(db)

    async def generate_stream():
        async for event in stream_service.stream_events(stream_input):
            payload = public_resume_stream_event(event)
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        },
    )


@router.post("/chat/confirm-tool")
async def confirm_tool(
    http_request: Request,
    request: ConfirmToolRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于接收前端对单个工具调用的确认或拒绝结果。"""
    with log_context(
        request_id=getattr(http_request.state, "request_id", None),
        session_id=request.session_id,
        tool_call_id=request.call_id,
    ):
        store = AgentSessionStore(db)
        service = ResumeAgentSessionService(
            store,
            confirmation_sessions=confirmation_manager,
        )
        try:
            result = await service.confirm_tool(
                session_id=request.session_id,
                call_id=request.call_id,
                confirmed=request.confirmed,
                user_id=current_user["id"],
            )
        except ResumeAgentSessionNotFound as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc
        except ResumeAgentConfirmationConflict as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc

        if result.ok and not result.duplicate:
            logger.info(
                "Resume agent tool confirmation received confirmed=%s",
                request.confirmed,
            )
        return result.to_response()


@router.post("/chat/resume-session")
async def resume_agent_session(
    http_request: Request,
    request: ResumeSessionRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于恢复因确认中断而暂停的简历 Agent session。"""
    with log_context(
        request_id=getattr(http_request.state, "request_id", None),
        session_id=request.session_id,
    ):
        service = ResumeAgentStreamService(db)
        return service.resume_session(
            session_id=request.session_id,
            user_id=current_user["id"],
        )


@router.get("/status")
async def get_ai_status():
    """用于返回当前 AI 聊天服务是否已完成配置。"""
    try:
        chat_service = ChatService()
        # 简单的状态检查
        if chat_service.api_key and chat_service.api_key.strip():
            return {
                "service": "openrouter",
                "status": "connected",
                "is_configured": True,
            }
        else:
            return {
                "service": "mock",
                "status": "not_configured",
                "is_configured": False,
            }
    except Exception:
        return {"service": "mock", "status": "error", "is_configured": False}
