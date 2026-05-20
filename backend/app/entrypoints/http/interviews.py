"""实时语音面试 session API。"""

from __future__ import annotations

from typing import Any, Dict, List, NoReturn, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.entrypoints.http.deps import get_current_user
from app.infra.database import get_db
from app.services.errors import (
    ServiceError,
    ServiceNotFoundError,
    ServicePermissionError,
    ServiceValidationError,
)
from app.services.interview.report_service import generate_interview_report
from app.services.interview.serializer import serialize_session
from app.services.interview.session_service import (
    create_interview_session,
    delete_interview_session,
    end_interview_session,
    get_session_for_user,
    list_interview_sessions,
    record_voice_interview_message,
)

router = APIRouter()


class InterviewCreateRequest(BaseModel):
    """用于承载创建实时语音面试 session 的请求参数。"""

    resume_id: int
    target_title: str = ""
    target_company: str = ""
    jd_text: str = ""
    interview_type: str = "general"
    difficulty: str = "medium"
    language: str = "zh-CN"
    mode: str = "practice"


class InterviewActionResponse(BaseModel):
    """用于统一返回面试动作后的最新 session 结果。"""

    session: Dict[str, Any]
    message: Optional[str] = None
    evaluation: Optional[str] = None
    next_action: Optional[str] = None


class InterviewMessageRecordRequest(BaseModel):
    """用于持久化实时语音面试中已经展示的最终文本。"""

    role: str
    text: str


def _raise_service_http_error(exc: ServiceError) -> NoReturn:
    """用于抛出服务HTTP错误。"""
    if isinstance(exc, ServicePermissionError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc
    if isinstance(exc, ServiceNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    if isinstance(exc, ServiceValidationError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
    ) from exc


@router.post("/", response_model=InterviewActionResponse)
async def create_interview(
    request: InterviewCreateRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于创建一场新的实时语音面试。"""
    try:
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
    except ServiceError as exc:
        _raise_service_http_error(exc)
    return InterviewActionResponse(
        session=serialize_session(session), next_action="voice"
    )


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
    try:
        session = get_session_for_user(db, session_id, current_user["id"])
    except ServiceError as exc:
        _raise_service_http_error(exc)
    return InterviewActionResponse(session=serialize_session(session))


@router.post("/{session_id}/messages", response_model=InterviewActionResponse)
async def record_interview_message(
    session_id: int,
    request: InterviewMessageRecordRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于把实时语音面试中已经展示的最终文本持久化。"""
    try:
        session = get_session_for_user(db, session_id, current_user["id"])
    except ServiceError as exc:
        _raise_service_http_error(exc)
    record_voice_interview_message(
        db=db,
        session_id=session_id,
        role=request.role,
        text=request.text,
    )
    db.refresh(session)
    return InterviewActionResponse(session=serialize_session(session))


@router.delete("/{session_id}", response_model=Dict[str, str])
async def delete_interview(
    session_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于删除当前用户的一场面试记录及其关联轮次。"""
    try:
        delete_interview_session(
            db=db, user_id=current_user["id"], session_id=session_id
        )
    except ServiceError as exc:
        _raise_service_http_error(exc)
    return {"message": "Interview session deleted"}


@router.post("/{session_id}/end", response_model=InterviewActionResponse)
async def end_interview(
    session_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于让用户主动结束当前面试。"""
    try:
        session = end_interview_session(
            db=db, user_id=current_user["id"], session_id=session_id
        )
    except ServiceError as exc:
        _raise_service_http_error(exc)
    return InterviewActionResponse(
        session=serialize_session(session), next_action="completed"
    )


@router.post("/{session_id}/report", response_model=InterviewActionResponse)
async def create_interview_report(
    session_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于为已完成面试生成评估报告。"""
    try:
        result = await generate_interview_report(
            db=db, user_id=current_user["id"], session_id=session_id
        )
    except ServiceError as exc:
        _raise_service_http_error(exc)
    return InterviewActionResponse(
        session=serialize_session(result.session),
        next_action="report" if result.generated else "report_skipped",
    )
