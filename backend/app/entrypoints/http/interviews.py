"""
结构化面试 API

用于提供结构化面试的 HTTP 路由入口，并把业务逻辑下沉到 service 层。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.entrypoints.http.deps import get_current_user
from app.infra.database import get_db
from app.services.interview.serializer import serialize_session
from app.services.interview.session_service import (
    answer_interview_session,
    create_interview_session,
    delete_interview_session,
    end_interview_session,
    get_interview_hints,
    get_session_or_404,
    list_interview_sessions,
    start_interview_session,
    stream_answer_interview_session,
)

router = APIRouter()


class InterviewCreateRequest(BaseModel):
    """用于承载创建结构化面试的请求参数。"""

    resume_id: int
    target_title: str = ""
    target_company: str = ""
    jd_text: str = ""
    interview_type: str = "general"
    difficulty: str = "medium"
    language: str = "zh-CN"
    mode: str = "practice"


class InterviewAnswerRequest(BaseModel):
    """用于承载候选人的一次作答内容。"""

    answer: str = Field(min_length=1)


class InterviewHintResponse(BaseModel):
    """用于返回练习模式下当前题目的提示内容。"""

    hints: List[str]


class InterviewActionResponse(BaseModel):
    """用于统一返回面试动作后的最新 session 结果。"""

    session: Dict[str, Any]
    message: Optional[str] = None
    evaluation: Optional[str] = None
    next_action: Optional[str] = None


@router.post("/", response_model=InterviewActionResponse)
async def create_interview(
    request: InterviewCreateRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于创建一场新的结构化模拟面试。"""
    session = create_interview_session(
        db=db,
        user_id=current_user["id"],
        resume_id=request.resume_id,
        target_title=request.target_title,
        target_company=request.target_company,
        jd_text=request.jd_text,
        interview_type=request.interview_type,
        difficulty=request.difficulty,
        language=request.language,
        mode=request.mode,
    )
    return InterviewActionResponse(
        session=serialize_session(session), next_action="start"
    )


@router.post("/{session_id}/hint", response_model=InterviewHintResponse)
async def get_interview_hint(
    session_id: int,
    http_request: Request,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于在练习模式下为当前题目生成简短提示。"""
    hints = await get_interview_hints(
        db=db,
        user_id=current_user["id"],
        session_id=session_id,
        http_request=http_request,
    )
    return InterviewHintResponse(hints=hints)


@router.get("/", response_model=List[Dict[str, Any]])
async def list_interviews(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于返回当前用户的面试 session 列表。"""
    return list_interview_sessions(db=db, user_id=current_user["id"])


@router.get("/{session_id}", response_model=InterviewActionResponse)
async def get_interview(
    session_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于返回单场面试的完整状态。"""
    session = get_session_or_404(db, session_id, current_user["id"])
    return InterviewActionResponse(session=serialize_session(session))


@router.delete("/{session_id}", response_model=Dict[str, str])
async def delete_interview(
    session_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于删除当前用户的一场面试记录及其关联轮次。"""
    delete_interview_session(db=db, user_id=current_user["id"], session_id=session_id)
    return {"message": "Interview session deleted"}


@router.post("/{session_id}/start", response_model=InterviewActionResponse)
async def start_interview(
    session_id: int,
    http_request: Request,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于启动一场待开始的面试并生成第一题。"""
    session, message, next_action = await start_interview_session(
        db=db,
        user_id=current_user["id"],
        session_id=session_id,
        http_request=http_request,
    )
    return InterviewActionResponse(
        session=serialize_session(session),
        message=message or None,
        next_action=next_action,
    )


@router.post("/{session_id}/answer", response_model=InterviewActionResponse)
async def answer_interview(
    session_id: int,
    request: InterviewAnswerRequest,
    http_request: Request,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于处理一次回答并生成下一题或结束面试。"""
    session, message, next_action = await answer_interview_session(
        db=db,
        user_id=current_user["id"],
        session_id=session_id,
        answer_text=request.answer.strip(),
        http_request=http_request,
    )
    return InterviewActionResponse(
        session=serialize_session(session),
        message=message,
        next_action=next_action,
    )


@router.post("/{session_id}/answer/stream")
async def answer_interview_stream(
    session_id: int,
    http_request: Request,
    request: InterviewAnswerRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于流式生成下一题并在结束时返回最新 session。"""
    return await stream_answer_interview_session(
        db=db,
        user_id=current_user["id"],
        session_id=session_id,
        answer_text=request.answer.strip(),
        http_request=http_request,
    )


@router.post("/{session_id}/end", response_model=InterviewActionResponse)
async def end_interview(
    session_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于让用户主动结束当前面试。"""
    session = end_interview_session(
        db=db, user_id=current_user["id"], session_id=session_id
    )
    return InterviewActionResponse(
        session=serialize_session(session), next_action="completed"
    )


@router.get("/{session_id}/report", response_model=InterviewActionResponse)
async def get_interview_report(
    session_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于返回指定面试的最终报告视图。"""
    session = get_session_or_404(db, session_id, current_user["id"])
    return InterviewActionResponse(session=serialize_session(session))
