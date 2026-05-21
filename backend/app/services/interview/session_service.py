"""实时语音面试 session 服务。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import case, func
from sqlalchemy.orm import Session, noload

from app.models import InterviewSession, InterviewTurn
from app.services.domain import ResumeService
from app.services.errors import ServiceNotFoundError, ServicePermissionError
from app.services.interview.serializer import serialize_session_summary


def now() -> datetime:
    """生成带时区的当前时间。"""
    return datetime.now(timezone.utc)


_INTERVIEW_PLAN_DIMENSIONS = [
    "岗位匹配度",
    "项目真实性",
    "技术深度",
    "表达结构",
    "风险点",
]

_INTERVIEW_PLAN_STAGES = [
    {
        "name": "开场和目标确认",
        "goal": "确认候选人目标岗位和最相关经历",
        "max_turns": 1,
    },
    {
        "name": "简历项目深挖",
        "goal": "验证简历主张、个人贡献、技术取舍和量化结果",
        "max_turns": 4,
    },
    {
        "name": "JD 能力匹配",
        "goal": "围绕岗位要求检查必备能力和迁移经验",
        "max_turns": 3,
    },
    {
        "name": "行为面试",
        "goal": "检查协作、冲突处理、抗压和复盘能力",
        "max_turns": 2,
    },
]


def _coerce_text(value: Any) -> str:
    """把简历字段转成可放入面试计划的短文本。"""
    if isinstance(value, list):
        return "；".join(str(item) for item in value if item)
    if value is None:
        return ""
    return str(value)


def _collect_resume_claims(resume_content: dict[str, Any]) -> list[str]:
    """从简历中抽取需要面试官验证的项目和经历主张。"""
    claims: list[str] = []
    for item in (resume_content.get("work_experience") or [])[:3]:
        title = _coerce_text(item.get("title") or item.get("position"))
        desc = _coerce_text(item.get("description") or item.get("responsibilities"))
        claim = " | ".join(part for part in [title, desc[:120]] if part)
        if claim:
            claims.append(claim)
    for item in (resume_content.get("projects") or [])[:3]:
        name = _coerce_text(item.get("name"))
        desc = _coerce_text(item.get("description"))[:120]
        claim = " | ".join(part for part in [name, desc] if part)
        if claim:
            claims.append(claim)
    return claims[:5]


def _build_interview_plan(
    *,
    target_title: str,
    target_company: str,
    jd_text: str,
    interview_type: str,
    difficulty: str,
    resume_content: dict[str, Any],
) -> dict[str, Any]:
    """生成实时面试使用的结构化计划。"""
    return {
        "target_role": target_title or "目标岗位",
        "target_company": target_company or "目标公司",
        "interview_type": interview_type,
        "difficulty": difficulty,
        "dimensions": list(_INTERVIEW_PLAN_DIMENSIONS),
        "stages": [dict(stage) for stage in _INTERVIEW_PLAN_STAGES],
        "resume_claims": _collect_resume_claims(resume_content),
        "jd_focus": jd_text[:400],
    }


def get_resume_for_user(db: Session, resume_id: int, user_id: int):
    """校验用户对目标简历的访问权限。"""
    resume = ResumeService(db).get_by_id(resume_id)
    if not resume:
        raise ServiceNotFoundError("Resume not found")
    if resume.owner_id != user_id:
        raise ServicePermissionError("Not enough permissions")
    return resume


def get_session_for_user(
    db: Session, session_id: int, user_id: int
) -> InterviewSession:
    """读取并校验当前用户拥有的面试 session。"""
    session = (
        db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    )
    if not session or session.user_id != user_id:
        raise ServiceNotFoundError("Interview session not found")
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

    resolved_title = target_title or str(job_application.get("target_title", "") or "")
    resolved_company = target_company or str(
        job_application.get("target_company", "") or ""
    )
    resolved_jd = jd_text or str(job_application.get("jd_text", "") or "")

    session = InterviewSession(
        user_id=user_id,
        resume_id=resume_id,
        target_title=resolved_title,
        target_company=resolved_company,
        jd_text=resolved_jd,
        interview_type=interview_type,
        difficulty=difficulty,
        language=language,
        mode=mode,
        status="interview_ready",
        current_round_index=0,
        current_turn_index=0,
        plan_json=_build_interview_plan(
            target_title=resolved_title,
            target_company=resolved_company,
            jd_text=resolved_jd,
            interview_type=interview_type,
            difficulty=difficulty,
            resume_content=resume_content,
        ),
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
    session = get_session_for_user(db, session_id, user_id)
    db.delete(session)
    db.commit()


def end_interview_session(
    *, db: Session, user_id: int, session_id: int
) -> InterviewSession:
    """主动结束当前实时语音面试。"""
    session = get_session_for_user(db, session_id, user_id)
    session.status = "completed"
    session.ended_at = now()
    db.commit()
    db.refresh(session)
    return session


def record_voice_interview_message(
    *,
    db: Session,
    session_id: int,
    role: str,
    text: str,
) -> InterviewTurn | None:
    """把实时语音面试文本落到 interview_turns。

    面试官消息作为 question，候选人消息作为最近一轮 question 的 answer。
    """
    content = text.strip()
    if not content:
        return None

    session = (
        db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    )
    if not session:
        return None

    latest = (
        db.query(InterviewTurn)
        .filter(InterviewTurn.session_id == session_id)
        .order_by(InterviewTurn.turn_index.desc())
        .first()
    )

    if role == "interviewer":
        if latest and latest.question.strip() == content:
            return latest

        next_turn_index = (latest.turn_index + 1) if latest else 0
        turn = InterviewTurn(
            session_id=session_id,
            turn_index=next_turn_index,
            round_index=session.current_round_index,
            question=content,
            question_type="voice",
            status="waiting_user_answer",
            asked_at=now(),
        )
        session.status = "waiting_user_answer"
        session.current_turn_index = next_turn_index
        if not session.started_at:
            session.started_at = now()
        db.add(turn)
        db.commit()
        db.refresh(turn)
        return turn

    if role == "candidate":
        if latest is None:
            latest = InterviewTurn(
                session_id=session_id,
                turn_index=0,
                round_index=session.current_round_index,
                question="语音面试回答",
                question_type="voice",
                status="answered",
                asked_at=now(),
            )
            db.add(latest)

        existing_answer = (latest.answer or "").strip()
        if existing_answer and content in existing_answer:
            return latest

        latest.answer = (
            f"{existing_answer}\n{content}" if existing_answer else content
        )
        latest.status = "answered"
        latest.answered_at = now()
        session.status = "in_progress"
        if not session.started_at:
            session.started_at = now()
        db.commit()
        db.refresh(latest)
        return latest

    return None
