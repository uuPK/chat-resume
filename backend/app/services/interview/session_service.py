"""实时语音面试 session 服务。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import case, func
from sqlalchemy.orm import Session, noload

from app.models import InterviewSession, InterviewTurn
from app.services.domain import ResumeService
from app.services.interview.serializer import serialize_session_summary


def now() -> datetime:
    """生成带时区的当前时间。"""
    return datetime.now(timezone.utc)


def get_resume_for_user(db: Session, resume_id: int, user_id: int):
    """校验用户对目标简历的访问权限。"""
    resume = ResumeService(db).get_by_id(resume_id)
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found"
        )
    if resume.owner_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )
    return resume


def get_session_or_404(db: Session, session_id: int, user_id: int) -> InterviewSession:
    """读取并校验当前用户拥有的面试 session。"""
    session = (
        db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    )
    if not session or session.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found"
        )
    return session


def create_interview_session(
    *,
    db: Session,
    user_id: int,
    resume_id: int,
    target_title: str,
    target_company: str,
    jd_text: str,
    interview_type: str,
    difficulty: str,
    language: str,
    mode: str,
) -> InterviewSession:
    """创建实时语音面试 session。"""
    resume = get_resume_for_user(db, resume_id, user_id)
    resume_content = resume.content if isinstance(resume.content, dict) else {}
    job_application = (
        (resume_content.get("job_application") or {})
        if isinstance(resume_content, dict)
        else {}
    )

    session = InterviewSession(
        user_id=user_id,
        resume_id=resume_id,
        target_title=target_title or str(job_application.get("target_title", "") or ""),
        target_company=target_company
        or str(job_application.get("target_company", "") or ""),
        jd_text=jd_text or str(job_application.get("jd_text", "") or ""),
        interview_type=interview_type,
        difficulty=difficulty,
        language=language,
        mode=mode,
        status="interview_ready",
        current_round_index=0,
        current_turn_index=0,
        plan_json=None,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def list_interview_sessions(*, db: Session, user_id: int) -> list[dict[str, Any]]:
    """返回当前用户的面试 session 列表。"""
    answered_turn_counts = (
        db.query(
            InterviewTurn.session_id.label("session_id"),
            func.sum(
                case(
                    (InterviewTurn.answer.isnot(None), 1),
                    else_=0,
                )
            ).label("answered_turn_count"),
        )
        .group_by(InterviewTurn.session_id)
        .subquery()
    )
    sessions = (
        db.query(
            InterviewSession,
            func.coalesce(answered_turn_counts.c.answered_turn_count, 0).label(
                "answered_turn_count"
            ),
        )
        .outerjoin(
            answered_turn_counts,
            answered_turn_counts.c.session_id == InterviewSession.id,
        )
        .options(noload(InterviewSession.turns))
        .filter(InterviewSession.user_id == user_id)
        .order_by(InterviewSession.id.desc())
        .all()
    )
    return [
        serialize_session_summary(
            session, answered_turn_count=int(answered_turn_count or 0)
        )
        for session, answered_turn_count in sessions
    ]


def delete_interview_session(*, db: Session, user_id: int, session_id: int) -> None:
    """删除当前用户的一场面试记录及其关联轮次。"""
    session = get_session_or_404(db, session_id, user_id)
    db.delete(session)
    db.commit()


def end_interview_session(
    *, db: Session, user_id: int, session_id: int
) -> InterviewSession:
    """主动结束当前实时语音面试。"""
    session = get_session_or_404(db, session_id, user_id)
    session.status = "completed"
    session.ended_at = now()
    db.commit()
    db.refresh(session)
    return session
