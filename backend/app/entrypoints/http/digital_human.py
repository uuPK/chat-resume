"""数字人 API 入口。

负责把面试上下文转换成 Tavus 会话请求，并隐藏供应商密钥。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.entrypoints.http.deps import get_current_user
from app.infra.config import settings
from app.infra.database import get_db
from app.models.interview import InterviewSession
from app.services.digital_human import (
    LiveAvatarConfigurationError,
    LiveAvatarService,
    TavusConfigurationError,
    TavusService,
    VolcengineConfigurationError,
    VolcengineVoiceService,
)
from app.services.interview.session_service import get_session_or_404

router = APIRouter()


class DigitalHumanCreateRequest(BaseModel):
    """用于承载创建数字人会话的请求参数。"""

    interview_session_id: int


class DigitalHumanEndRequest(BaseModel):
    """用于承载结束数字人会话的请求参数。"""

    conversation_id: str


class DigitalHumanConversationResponse(BaseModel):
    """用于返回前端可安全使用的数字人会话信息。"""

    provider: str
    conversation_id: str = ""
    conversation_url: str = ""
    join_url: str = ""
    session_id: str = ""
    session_token: str = ""
    status: str
    meeting_token: Optional[str] = None


@router.post("/conversations", response_model=DigitalHumanConversationResponse)
async def create_digital_human_conversation(
    request: DigitalHumanCreateRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于为一场面试创建真实 Tavus 数字人视频会话。"""
    session = get_session_or_404(db, request.interview_session_id, current_user["id"])
    target_title = session.target_title or "目标岗位"
    target_company = session.target_company or "目标公司"
    conversation_name = f"Interview #{session.id}: {target_title}"
    context = _build_interview_context(
        target_title=target_title,
        target_company=target_company,
        language=session.language,
        difficulty=session.difficulty,
        jd_text=session.jd_text or "",
    )
    greeting = _build_greeting(
        target_title=target_title,
        target_company=target_company,
        language=session.language,
    )

    provider = settings.DIGITAL_HUMAN_PROVIDER.strip().lower()
    if provider == "volcengine":
        return DigitalHumanConversationResponse(
            provider="volcengine",
            session_id=str(request.interview_session_id),
            status="ready",
        )

    if provider in {"heygen", "liveavatar", "heygen-liveavatar"}:
        service = LiveAvatarService()
        try:
            return await service.create_session(
                language=session.language,
                dynamic_variables={
                    "target_title": target_title,
                    "target_company": target_company,
                    "language": session.language,
                    "difficulty": session.difficulty,
                },
            )
        except LiveAvatarConfigurationError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc
        except httpx.HTTPStatusError as exc:
            detail = _extract_tavus_error(exc.response)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"LiveAvatar session creation failed: {detail}",
            ) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"LiveAvatar request failed: {str(exc)}",
            ) from exc

    service = TavusService()
    try:
        return await service.create_conversation(
            conversation_name=conversation_name,
            conversational_context=context,
            custom_greeting=greeting,
        )
    except TavusConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except httpx.HTTPStatusError as exc:
        detail = _extract_tavus_error(exc.response)
        if exc.response.status_code == status.HTTP_402_PAYMENT_REQUIRED:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Tavus conversational credits are exhausted: {detail}",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Tavus conversation creation failed: {detail}",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Tavus request failed: {str(exc)}",
        ) from exc


@router.post("/conversations/end", response_model=Dict[str, str])
async def end_digital_human_conversation(
    request: DigitalHumanEndRequest,
    current_user: dict = Depends(get_current_user),
):
    """用于主动关闭 Tavus 数字人会话，释放供应商侧资源。"""
    provider = settings.DIGITAL_HUMAN_PROVIDER.strip().lower()
    if provider == "volcengine":
        return {"message": "Volcengine voice sessions are closed by the WebSocket proxy"}

    if provider in {"heygen", "liveavatar", "heygen-liveavatar"}:
        return {"message": "LiveAvatar sessions are closed by the browser SDK"}

    service = TavusService()
    try:
        await service.end_conversation(request.conversation_id)
    except TavusConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except httpx.HTTPStatusError as exc:
        detail = _extract_tavus_error(exc.response)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Tavus conversation end failed: {detail}",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Tavus request failed: {str(exc)}",
        ) from exc
    return {"message": "Digital human conversation ended"}


def _build_interview_context(
    *,
    target_title: str,
    target_company: str,
    language: str,
    difficulty: str,
    jd_text: str,
) -> str:
    """用于把结构化面试信息整理成 Tavus persona 的会话上下文。"""
    if _prefers_chinese(language):
        context = (
            "你是一位专业、自然、支持性的中文模拟面试官。"
            "除非候选人明确要求英文，否则你必须全程使用中文普通话。"
            "你的目标是模拟真实招聘面试：先提出简洁问题，等待候选人回答，"
            "再根据回答进行追问或简短反馈。"
            f"候选人正在准备 {target_company} 的 {target_title} 岗位。"
            f"面试难度：{difficulty}。"
        )
        if jd_text:
            context += f"\n岗位 JD 信息：\n{jd_text[:4000]}"
        return context

    context = (
        "You are a professional mock interviewer in a hiring interview room. "
        "Keep the tone natural, focused, and supportive. "
        f"The candidate is practicing for {target_title} at {target_company}. "
        f"Interview language: {language}. Difficulty: {difficulty}. "
        "Ask concise questions and wait for the candidate to answer."
    )
    if jd_text:
        context += f"\nJob description context:\n{jd_text[:4000]}"
    return context


def _build_greeting(
    *, target_title: str, target_company: str, language: str
) -> str:
    """用于生成数字人进入房间后的第一句欢迎语。"""
    if _prefers_chinese(language):
        return (
            "欢迎来到模拟面试。"
            f"今天我们会围绕你申请的 {target_company} 的 {target_title} 岗位展开。"
            "准备好后，我们就开始。"
        )
    return (
        "Welcome to your mock interview. "
        f"We will focus on the {target_title} role at {target_company}. "
        "Let's begin when you are ready."
    )


def _prefers_chinese(language: str) -> bool:
    """用于根据 session 语言判断 Tavus 是否应使用中文。"""
    normalized = language.strip().lower()
    return normalized.startswith("zh") or "chinese" in normalized or "中文" in language


def _build_volcengine_system_role(
    *,
    target_title: str,
    target_company: str,
    language: str,
    difficulty: str,
    jd_text: str,
) -> str:
    """用于构建火山引擎 O 版本的 system_role。"""
    if _prefers_chinese(language):
        role = (
            "你是一位专业、自然、支持性的中文模拟面试官。"
            "除非候选人明确要求英文，否则你必须全程使用中文普通话。"
            "你的目标是模拟真实招聘面试：先提出简洁问题，等待候选人回答，"
            "再根据回答进行追问或简短反馈。"
            f"候选人正在准备 {target_company} 的 {target_title} 岗位。"
            f"面试难度：{difficulty}。"
        )
        if jd_text:
            role += f"\n岗位 JD 信息：\n{jd_text[:3000]}"
        return role

    role = (
        "You are a professional mock interviewer in a hiring interview room. "
        "Keep the tone natural, focused, and supportive. "
        f"The candidate is practicing for {target_title} at {target_company}. "
        f"Interview language: {language}. Difficulty: {difficulty}. "
        "Ask concise questions and wait for the candidate to answer."
    )
    if jd_text:
        role += f"\nJob description context:\n{jd_text[:3000]}"
    return role


@router.websocket("/voice-session/{session_id}")
async def voice_session_ws(
    websocket: WebSocket,
    session_id: int,
    db: Session = Depends(get_db),
):
    """用于在前端和火山引擎之间代理实时语音 WebSocket 连接。"""
    await websocket.accept()
    logger.info("Voice WebSocket accepted for interview_session_id=%s", session_id)
    service = VolcengineVoiceService()
    if not service.is_configured():
        logger.warning("Voice WebSocket closed because Volcengine is not configured")
        await websocket.send_json({"type": "error", "message": "火山引擎未配置"})
        await websocket.close()
        return

    # 加载面试上下文构建 system_role
    system_role = ""
    interview_session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if interview_session:
        system_role = _build_volcengine_system_role(
            target_title=interview_session.target_title or "目标岗位",
            target_company=interview_session.target_company or "目标公司",
            language=interview_session.language,
            difficulty=interview_session.difficulty,
            jd_text=interview_session.jd_text or "",
        )

    try:
        await service.proxy_session(client_ws=websocket, system_role=system_role)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.exception("Volcengine voice proxy error")
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


def _extract_tavus_error(response: httpx.Response) -> Any:
    """用于从 Tavus 错误响应中提取可读信息。"""
    try:
        return response.json()
    except ValueError:
        return response.text
