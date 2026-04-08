"""面试管理 API 端点模块。"""

import json
import logging
from typing import Any, Dict, List, Optional, cast

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_current_user_claims
from app.core.database import get_db
from app.models.resume import InterviewSession, Resume
from app.schemas.interview import (
    InterviewSessionCreate,
    InterviewAnswerRequest,
    InterviewEvaluationResponse,
    InterviewQuestionResponse,
    InterviewSessionResponse,
    InterviewTurn,
)
from app.services.core import ResumeService

logger = logging.getLogger(__name__)

router = APIRouter()

DEFAULT_MAX_TURNS = 5


def _safe_json_loads(value: str) -> Optional[Dict[str, Any]]:
    if not isinstance(value, str):
        return None

    candidate = value.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        candidate = "\n".join(lines).strip()

    if "```" in candidate:
        candidate = candidate.replace("```json", "").replace("```", "").strip()

    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    return None


def _build_default_evaluation(text: str) -> Dict[str, Any]:
    return {
        "score": 7,
        "feedback": text,
        "improvements": [
            "建议回答时先给出结论，再补充背景和行动细节",
            "补充量化结果或具体案例来增强说服力",
        ],
    }


def _serialize_turn(turn: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "turn_index": int(turn.get("turn_index", 0)),
        "question": str(turn.get("question", "")),
        "question_type": str(turn.get("question_type", "general")),
        "intent": turn.get("intent"),
        "answer": turn.get("answer"),
        "evaluation": turn.get("evaluation"),
        "score": turn.get("score"),
        "status": str(turn.get("status", "asked")),
    }


def _normalize_turns(interview_session: InterviewSession) -> List[Dict[str, Any]]:
    raw_questions = list(cast(List[Any], interview_session.questions) or [])
    raw_answers = list(cast(List[Any], interview_session.answers) or [])
    turns: List[Dict[str, Any]] = []

    for index, raw in enumerate(raw_questions):
        if isinstance(raw, dict) and "turn_index" in raw and "question" in raw:
            turns.append(_serialize_turn(raw))
            continue

        question = ""
        question_type = "general"
        answer = None
        evaluation = None
        score = None
        status = "asked"

        if isinstance(raw, dict):
            question = str(raw.get("question", raw.get("ai_response", "")))
            question_type = str(raw.get("type", "general"))
            if raw.get("user_message"):
                answer = str(raw["user_message"])
                status = "answered"
        else:
            question = str(raw)

        if index < len(raw_answers) and isinstance(raw_answers[index], dict):
            answer_item = raw_answers[index]
            answer = answer or answer_item.get("answer")
            evaluation = answer_item.get("evaluation")
            score = (
                answer_item.get("score")
                if answer_item.get("score") is not None
                else (evaluation or {}).get("score")
            )
            if answer:
                status = "answered"

        turns.append(
            _serialize_turn(
                {
                    "turn_index": index,
                    "question": question,
                    "question_type": question_type,
                    "answer": answer,
                    "evaluation": evaluation,
                    "score": score,
                    "status": status,
                }
            )
        )

    return turns


def _sync_session_turns(
    interview_session: InterviewSession, turns: List[Dict[str, Any]]
) -> None:
    serialized_turns = [_serialize_turn(turn) for turn in turns]
    answer_rows: List[Dict[str, Any]] = []
    for turn in serialized_turns:
        if turn.get("answer"):
            answer_rows.append(
                {
                    "answer": turn["answer"],
                    "question_index": turn["turn_index"],
                    "evaluation": turn.get("evaluation"),
                    "score": turn.get("score"),
                }
            )

    interview_session.questions = serialized_turns  # type: ignore
    interview_session.answers = answer_rows  # type: ignore


def _current_turn_from(turns: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for turn in turns:
        if turn.get("status") != "answered":
            return turn
    return None


def _build_session_response(
    interview_session: InterviewSession, resume_title: Optional[str] = None
) -> InterviewSessionResponse:
    turns = _normalize_turns(interview_session)
    current_turn = _current_turn_from(turns)
    answered_questions = sum(1 for turn in turns if turn.get("answer"))
    payload = {
        **InterviewSessionResponse.model_validate(interview_session).model_dump(),
        "resume_title": resume_title,
        "turns": [InterviewTurn.model_validate(turn) for turn in turns],
        "current_turn": (
            InterviewTurn.model_validate(current_turn) if current_turn else None
        ),
        "total_questions": len(turns),
        "answered_questions": answered_questions,
        "overall_score": getattr(interview_session, "overall_score", None),
    }
    return InterviewSessionResponse.model_validate(payload)


def _get_max_turns(interview_session: InterviewSession) -> int:
    feedback = cast(Dict[str, Any], interview_session.feedback) or {}
    plan = feedback.get("plan", {}) if isinstance(feedback, dict) else {}
    max_turns = plan.get("max_turns", DEFAULT_MAX_TURNS)
    return max(1, int(max_turns))


def _opening_question(job_title: Optional[str]) -> str:
    if job_title:
        return (
            f"请先做一个 1-2 分钟的自我介绍，并重点说明你与 {job_title} "
            "这个岗位最相关的经历。"
        )
    return "请先做一个 1-2 分钟的自我介绍，并重点说明你最近一段最有代表性的工作经历。"


async def _generate_next_turn(
    interview_session: InterviewSession,
    resume: Resume,
    turns: List[Dict[str, Any]],
) -> Dict[str, Any]:
    from app.services.ai import InterviewAgent

    interview_agent = InterviewAgent()
    history_lines = []
    for turn in turns:
        history_lines.append(f"问题：{turn.get('question', '')}")
        history_lines.append(f"回答：{turn.get('answer', '')}")

    prompt = f"""你是一名结构化面试官。请基于已有问答生成下一题。

要求：
1. 只输出 JSON
2. JSON 格式必须为 {{"question":"...", "question_type":"...", "intent":"..."}}
3. question_type 只能是 opening, experience, technical, behavioral, situational, follow_up 之一
4. 问题必须简洁、单一，不要一次问多个子问题

已知岗位：{interview_session.job_position or "未指定"}
JD：
{interview_session.jd_content or ""}

历史问答：
{chr(10).join(history_lines)}
"""
    response = await interview_agent.chat(
        message=prompt,
        job_title=str(interview_session.job_position)
        if interview_session.job_position is not None
        else None,
        job_description=str(interview_session.jd_content)
        if interview_session.jd_content is not None
        else None,
        resume_content=str(resume.content) if resume.content is not None else None,
        conversation_history=[],
    )
    parsed = _safe_json_loads(response) or {}
    return _serialize_turn(
        {
            "turn_index": len(turns),
            "question": parsed.get("question")
            or "请结合一个具体案例，进一步说明你的个人贡献和实际结果。",
            "question_type": parsed.get("question_type", "follow_up"),
            "intent": parsed.get("intent", "继续深入评估候选人的真实经验"),
            "status": "asked",
        }
    )


async def _evaluate_answer(
    interview_session: InterviewSession,
    resume: Resume,
    turn: Dict[str, Any],
    answer: str,
) -> Dict[str, Any]:
    from app.services.ai import InterviewAgent

    interview_agent = InterviewAgent()
    prompt = f"""你是一名专业面试官，请评估以下回答。

要求：
1. 只输出 JSON
2. JSON 格式必须为 {{"score": 0-10 的整数, "feedback": "...", "improvements": ["...", "..."]}}
3. feedback 控制在 2-4 句话，直接指出优缺点
4. improvements 给出 2 条可执行建议

问题：{turn.get("question", "")}
候选人回答：{answer}
"""
    response = await interview_agent.chat(
        message=prompt,
        job_title=str(interview_session.job_position)
        if interview_session.job_position is not None
        else None,
        job_description=str(interview_session.jd_content)
        if interview_session.jd_content is not None
        else None,
        resume_content=str(resume.content) if resume.content is not None else None,
        conversation_history=[],
    )
    return _safe_json_loads(response) or _build_default_evaluation(response)


async def _generate_report(
    interview_session: InterviewSession,
    resume: Resume,
    turns: List[Dict[str, Any]],
    resume_title: Optional[str],
) -> Dict[str, Any]:
    from app.services.ai import InterviewAgent

    answered_turns = [turn for turn in turns if turn.get("answer")]
    avg_score = 0
    if answered_turns:
        avg_score = round(
            sum(int(turn.get("score") or 0) for turn in answered_turns)
            / len(answered_turns)
            * 10
        )

    fallback_report = {
        "id": interview_session.id,
        "resume_title": resume_title or "",
        "job_position": interview_session.job_position or "未指定职位",
        "interview_mode": "structured_interview",
        "jd_content": interview_session.jd_content or "",
        "overall_score": avg_score,
        "performance_level": "良好" if avg_score >= 75 else "需改进",
        "interview_date": str(interview_session.created_at),
        "duration_minutes": max(1, len(answered_turns) * 3) if answered_turns else 0,
        "total_questions": len(turns),
        "answered_questions": len(answered_turns),
        "competency_scores": {
            "job_fit": avg_score,
            "technical_depth": avg_score,
            "project_exposition": avg_score,
            "communication": avg_score,
            "behavioral": avg_score,
        },
        "ai_highlights": [],
        "ai_improvements": [],
        "conversation": [
            {
                "question": turn.get("question", ""),
                "answer": turn.get("answer", ""),
                "ai_feedback": {
                    "score": int(turn.get("score") or 0) * 10,
                    "strengths": [],
                    "suggestions": (turn.get("evaluation") or {}).get(
                        "improvements", []
                    ),
                },
            }
            for turn in answered_turns
        ],
        "all_questions": [
            {
                "question": turn.get("question", ""),
                "type": turn.get("question_type", "general"),
                "index": turn.get("turn_index", index),
            }
            for index, turn in enumerate(turns)
        ],
        "reference_answers": [],
        "jd_keywords": [],
        "coverage_rate": 0,
        "frequent_words": [],
    }

    if not answered_turns:
        fallback_report["ai_improvements"] = ["面试尚未形成有效问答，建议先完成至少 2 轮回答。"]
        return fallback_report

    interview_agent = InterviewAgent()
    transcript = _format_interview_session(answered_turns)
    prompt = f"""你是一名专业面试官，请基于以下结构化面试记录输出 JSON 报告。

必须只输出 JSON，格式如下：
{{
  "overall_score": 0-100,
  "performance_level": "...",
  "competency_scores": {{
    "job_fit": 0-100,
    "technical_depth": 0-100,
    "project_exposition": 0-100,
    "communication": 0-100,
    "behavioral": 0-100
  }},
  "ai_highlights": ["...", "..."],
  "ai_improvements": ["...", "..."]
}}

岗位：{interview_session.job_position or "未指定"}
JD：
{interview_session.jd_content or ""}

面试记录：
{transcript}
"""
    response = await interview_agent.chat(
        message=prompt,
        job_title=str(interview_session.job_position)
        if interview_session.job_position is not None
        else None,
        job_description=str(interview_session.jd_content)
        if interview_session.jd_content is not None
        else None,
        resume_content=str(resume.content) if resume.content is not None else None,
        conversation_history=[],
    )
    parsed = _safe_json_loads(response)
    if not parsed:
        fallback_report["ai_improvements"] = _build_default_evaluation(response)[
            "improvements"
        ]
        fallback_report["ai_highlights"] = ["系统已生成基础报告，建议进一步人工复盘。"]
        return fallback_report

    fallback_report["overall_score"] = int(parsed.get("overall_score", avg_score))
    fallback_report["performance_level"] = parsed.get(
        "performance_level", fallback_report["performance_level"]
    )
    fallback_report["competency_scores"] = parsed.get(
        "competency_scores", fallback_report["competency_scores"]
    )
    fallback_report["ai_highlights"] = parsed.get("ai_highlights", [])
    fallback_report["ai_improvements"] = parsed.get("ai_improvements", [])
    return fallback_report


def _format_interview_session(session_data: List[Dict[str, Any]]) -> str:
    """格式化面试会话数据为可读字符串"""
    formatted = []
    for i, item in enumerate(session_data, 1):
        formatted.append(f"问题{i}: {item.get('question', '')}")
        formatted.append(f"回答{i}: {item.get('answer', '')}")
        formatted.append("---")
    return "\n".join(formatted)


@router.get("/interview/sessions", response_model=List[InterviewSessionResponse])
async def get_all_interview_sessions(
    current_user: dict = Depends(get_current_user_claims),
    db: Session = Depends(get_db),
):
    """获取当前用户的全部面试会话列表。"""
    sessions = (
        db.query(InterviewSession)
        .join(Resume, InterviewSession.resume_id == Resume.id)
        .filter(Resume.owner_id == current_user["id"])
        .order_by(InterviewSession.created_at.desc())
        .all()
    )

    return [
        _build_session_response(session, session.resume.title if session.resume else None)
        for session in sessions
    ]


@router.post("/{resume_id}/interview/start", response_model=InterviewSessionResponse)
async def start_interview(
    resume_id: int,
    session_create: InterviewSessionCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """开始面试会话"""

    # 验证简历权限
    resume_service = ResumeService(db)
    resume = resume_service.get_by_id(resume_id)

    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found"
        )

    if resume.owner_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    # 检查是否已有进行中的面试会话
    existing_active_session = (
        db.query(InterviewSession)
        .filter(
            InterviewSession.resume_id == resume_id, InterviewSession.status == "active"
        )
        .first()
    )

    if existing_active_session:
        # 自动结束旧的活跃会话，以便创建新会话
        logger.info(
            f"发现现有活跃会话 {existing_active_session.id}，自动结束旧会话以创建新会话"
        )
        existing_active_session.status = "completed"  # type: ignore
        db.commit()

    try:
        first_turn = _serialize_turn(
            {
                "turn_index": 0,
                "question": _opening_question(session_create.job_position),
                "question_type": "opening",
                "intent": "建立候选人的背景信息，并确认与目标岗位的相关性",
                "status": "asked",
            }
        )

        interview_session = InterviewSession(
            resume_id=resume_id,
            job_position=session_create.job_position,
            jd_content=session_create.jd_content,
            questions=[first_turn],
            answers=[],
            feedback={
                "mode": "structured_interview",
                "plan": {"max_turns": DEFAULT_MAX_TURNS},
            },
            status="active",
        )
        db.add(interview_session)
        db.commit()
        db.refresh(interview_session)

        return _build_session_response(interview_session, resume.title)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start interview: {str(e)}",
        )


@router.get(
    "/{resume_id}/interview/{session_id}/question",
    response_model=InterviewQuestionResponse,
)
async def get_next_question(
    resume_id: int,
    session_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取下一个面试问题"""

    # 验证权限
    interview_session = (
        db.query(InterviewSession)
        .filter(
            InterviewSession.id == session_id, InterviewSession.resume_id == resume_id
        )
        .first()
    )

    if not interview_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found"
        )

    # 验证简历权限
    resume_service = ResumeService(db)
    resume = resume_service.get_by_id(resume_id)

    if resume.owner_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    turns = _normalize_turns(interview_session)
    current_turn = _current_turn_from(turns)

    if current_turn:
        return InterviewQuestionResponse.model_validate(
            {
                "question": current_turn["question"],
                "question_type": current_turn.get("question_type", "general"),
                "question_index": current_turn["turn_index"],
            }
        )

    try:
        if len(turns) >= _get_max_turns(interview_session):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Interview has reached the maximum number of questions",
            )

        next_turn = await _generate_next_turn(interview_session, resume, turns)
        turns.append(next_turn)
        _sync_session_turns(interview_session, turns)
        db.commit()

        return InterviewQuestionResponse.model_validate(
            {
                "question": next_turn["question"],
                "question_type": next_turn.get("question_type", "follow_up"),
                "question_index": next_turn["turn_index"],
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate next question: {str(e)}",
        )


@router.post(
    "/{resume_id}/interview/{session_id}/answer",
    response_model=InterviewEvaluationResponse,
)
async def submit_answer(
    resume_id: int,
    session_id: int,
    answer_request: InterviewAnswerRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """提交面试答案并获取评估"""

    # 验证权限
    interview_session = (
        db.query(InterviewSession)
        .filter(
            InterviewSession.id == session_id, InterviewSession.resume_id == resume_id
        )
        .first()
    )

    if not interview_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found"
        )

    # 验证简历权限
    resume_service = ResumeService(db)
    resume = resume_service.get_by_id(resume_id)

    if resume.owner_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    try:
        turns = _normalize_turns(interview_session)
        current_turn = _current_turn_from(turns)
        question_index = (
            current_turn["turn_index"] if current_turn else answer_request.question_index
        )

        if question_index >= len(turns):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid question index"
            )

        turn = turns[question_index]
        if turn.get("status") == "answered":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current interview question has already been answered",
            )

        evaluation = await _evaluate_answer(
            interview_session, resume, turn, answer_request.answer
        )

        turn["answer"] = answer_request.answer
        turn["evaluation"] = evaluation
        turn["score"] = int(evaluation.get("score", 7))
        turn["status"] = "answered"

        next_turn: Optional[Dict[str, Any]] = None
        answered_count = sum(1 for item in turns if item.get("answer"))
        max_turns = _get_max_turns(interview_session)
        if answered_count < max_turns:
            next_turn = await _generate_next_turn(interview_session, resume, turns)
            turns.append(next_turn)
            interview_session.status = "active"  # type: ignore
        else:
            interview_session.status = "completed"  # type: ignore

        _sync_session_turns(interview_session, turns)
        interview_session.report_data = None  # type: ignore
        db.commit()

        return InterviewEvaluationResponse.model_validate(
            {
                "question": turn["question"],
                "answer": answer_request.answer,
                "evaluation": evaluation,
                "score": evaluation.get("score", 7),
                "feedback": evaluation.get("feedback", ""),
                "suggestions": evaluation.get("improvements", []),
                "session_status": str(interview_session.status),
                "completed": interview_session.status == "completed",
                "current_turn": (
                    InterviewTurn.model_validate(next_turn) if next_turn else None
                ),
                "next_turn": (
                    InterviewTurn.model_validate(next_turn) if next_turn else None
                ),
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to evaluate answer: {str(e)}",
        )


@router.post("/{resume_id}/interview/{session_id}/end")
async def end_interview(
    resume_id: int,
    session_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """结束面试会话"""

    # 验证权限
    interview_session = (
        db.query(InterviewSession)
        .filter(
            InterviewSession.id == session_id, InterviewSession.resume_id == resume_id
        )
        .first()
    )

    if not interview_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found"
        )

    # 验证简历权限
    resume_service = ResumeService(db)
    resume = resume_service.get_by_id(resume_id)

    if resume.owner_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    try:
        turns = _normalize_turns(interview_session)
        report = await _generate_report(interview_session, resume, turns, resume.title)
        overall_score = int(report.get("overall_score", 0))
        interview_session.status = "completed"  # type: ignore
        setattr(interview_session, "overall_score", overall_score)
        interview_session.report_data = report  # type: ignore
        db.commit()

        return {
            "message": "Interview session ended successfully",
            "overall_score": overall_score,
        }

    except Exception as e:
        # 即使分数计算失败，也要结束面试
        interview_session.status = "completed"  # type: ignore

        db.commit()

        return {
            "message": "Interview session ended successfully",
            "warning": f"Failed to calculate overall score: {str(e)}",
        }


@router.get(
    "/{resume_id}/interview/sessions", response_model=List[InterviewSessionResponse]
)
async def get_interview_sessions(
    resume_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取面试会话列表"""

    # 验证简历权限
    resume_service = ResumeService(db)
    resume = resume_service.get_by_id(resume_id)

    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found"
        )

    if resume.owner_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    # 获取面试会话
    sessions = (
        db.query(InterviewSession)
        .filter(InterviewSession.resume_id == resume_id)
        .order_by(InterviewSession.created_at.desc())
        .all()
    )

    return [_build_session_response(session, resume.title) for session in sessions]


@router.get(
    "/{resume_id}/interview/{session_id}", response_model=InterviewSessionResponse
)
async def get_interview_session(
    resume_id: int,
    session_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取单个面试会话详情。"""

    resume_service = ResumeService(db)
    resume = resume_service.get_by_id(resume_id)
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found"
        )
    if resume.owner_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    session = (
        db.query(InterviewSession)
        .filter(InterviewSession.id == session_id, InterviewSession.resume_id == resume_id)
        .first()
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found"
        )

    return _build_session_response(session, resume.title)


@router.delete("/{resume_id}/interview/{session_id}")
async def delete_interview_session(
    resume_id: int,
    session_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除面试会话"""

    # 验证面试会话是否存在
    interview_session = (
        db.query(InterviewSession)
        .filter(
            InterviewSession.id == session_id, InterviewSession.resume_id == resume_id
        )
        .first()
    )

    if not interview_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found"
        )

    # 验证简历权限
    resume_service = ResumeService(db)
    resume = resume_service.get_by_id(resume_id)

    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found"
        )

    if resume.owner_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    # 删除面试会话
    db.delete(interview_session)
    db.commit()

    return {"message": "Interview session deleted successfully"}


@router.post("/{resume_id}/interview/calculate-scores")
async def calculate_scores_for_completed_interviews(
    resume_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """为已完成但没有分数的面试计算分数"""

    # 验证简历权限
    resume_service = ResumeService(db)
    resume = resume_service.get_by_id(resume_id)

    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found"
        )

    if resume.owner_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    # 查找已完成但没有分数的面试
    sessions = (
        db.query(InterviewSession)
        .filter(
            InterviewSession.resume_id == resume_id,
            InterviewSession.status == "completed",
            InterviewSession.overall_score.is_(None),
        )
        .all()
    )

    if not sessions:
        return {"message": "No interviews need score calculation", "updated_count": 0}

    updated_count = 0

    for session in sessions:
        try:
            turns = _normalize_turns(session)
            report = await _generate_report(session, resume, turns, resume.title)
            overall_score = int(report.get("overall_score", 0))

            if overall_score > 0:  # 只有成功计算出分数才更新
                setattr(session, "overall_score", overall_score)
                session.report_data = report  # type: ignore
                updated_count += 1

        except Exception as e:
            logger.error(f"Failed to calculate score for session {session.id}: {e}")
            continue

    if updated_count > 0:
        db.commit()

    return {
        "message": f"Successfully calculated scores for {updated_count} interviews",
        "updated_count": updated_count,
    }


@router.post("/{resume_id}/interview/cleanup-duplicate")
async def cleanup_duplicate_sessions(
    resume_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """清理重复的面试会话"""

    # 验证简历权限
    resume_service = ResumeService(db)
    resume = resume_service.get_by_id(resume_id)

    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found"
        )

    if resume.owner_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    # 查找重复的面试会话（同一简历的多个活跃会话）
    active_sessions = (
        db.query(InterviewSession)
        .filter(
            InterviewSession.resume_id == resume_id, InterviewSession.status == "active"
        )
        .order_by(InterviewSession.created_at.desc())
        .all()
    )

    cleaned_count = 0

    if len(active_sessions) > 1:
        # 保留最新的会话，删除其他的
        sessions_to_delete = active_sessions[1:]  # 跳过第一个（最新的）

        for session in sessions_to_delete:
            # 只删除没有答案的空会话
            session_answers = cast(List[Any], session.answers)
            if not session_answers or len(session_answers) == 0:
                db.delete(session)
                cleaned_count += 1
                logger.info(f"删除空的重复面试会话: {session.id}")

    if cleaned_count > 0:
        db.commit()

    return {
        "message": f"Cleaned up {cleaned_count} duplicate interview sessions",
        "cleaned_count": cleaned_count,
    }


@router.get("/{resume_id}/interview/{session_id}/report")
async def get_interview_report(
    resume_id: int,
    session_id: int,
    regenerate: bool = False,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取面试详细报告"""

    # 验证面试会话是否存在
    interview_session = (
        db.query(InterviewSession)
        .filter(
            InterviewSession.id == session_id, InterviewSession.resume_id == resume_id
        )
        .first()
    )

    if not interview_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found"
        )

    # 验证简历权限
    resume_service = ResumeService(db)
    resume = resume_service.get_by_id(resume_id)

    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found"
        )

    if resume.owner_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    # 检查面试状态 - 允许进行中和已完成的面试查看报告
    if interview_session.status not in ["active", "completed"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Interview must be active or completed to generate report",
        )

    try:
        # 检查是否已有缓存的报告（如果不是强制重新生成）
        report_data = cast(Dict[str, Any], interview_session.report_data)
        if report_data and not regenerate:
            logger.info(f"返回缓存的报告，面试会话ID: {session_id}")
            return report_data

        turns = _normalize_turns(interview_session)
        report = await _generate_report(interview_session, resume, turns, resume.title)

        # 缓存报告到数据库
        interview_session.report_data = report  # type: ignore
        interview_session.overall_score = int(report.get("overall_score", 0))  # type: ignore
        db.commit()
        logger.info(f"生成并缓存了新报告，面试会话ID: {session_id}")

        return report

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Generate report error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate report: {str(e)}",
        )


class InterviewChatRequest(BaseModel):
    """面试对话请求"""

    message: str
    chat_history: List[Dict[str, str]] = []


class InterviewChatResponse(BaseModel):
    """面试对话响应"""

    response: str


@router.post(
    "/{resume_id}/interview/{session_id}/chat",
    response_model=InterviewChatResponse,
)
async def interview_chat(
    resume_id: int,
    session_id: int,
    chat_request: InterviewChatRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """兼容旧版聊天接口，内部转到结构化问答链路。"""

    # 验证权限
    interview_session = (
        db.query(InterviewSession)
        .filter(
            InterviewSession.id == session_id, InterviewSession.resume_id == resume_id
        )
        .first()
    )

    if not interview_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found"
        )

    # 验证简历权限
    resume_service = ResumeService(db)
    resume = resume_service.get_by_id(resume_id)

    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found"
        )

    if resume.owner_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    try:
        turns = _normalize_turns(interview_session)
        current_turn = _current_turn_from(turns)
        if not current_turn:
            return InterviewChatResponse(response="本场面试已完成，请查看面试报告。")

        evaluation = await _evaluate_answer(
            interview_session, resume, current_turn, chat_request.message
        )
        current_turn["answer"] = chat_request.message
        current_turn["evaluation"] = evaluation
        current_turn["score"] = int(evaluation.get("score", 7))
        current_turn["status"] = "answered"

        if sum(1 for turn in turns if turn.get("answer")) < _get_max_turns(interview_session):
            next_turn = await _generate_next_turn(interview_session, resume, turns)
            turns.append(next_turn)
            response = next_turn["question"]
        else:
            interview_session.status = "completed"  # type: ignore
            response = "本场模拟面试已完成。你可以结束面试并查看报告。"

        _sync_session_turns(interview_session, turns)
        interview_session.report_data = None  # type: ignore
        db.commit()
        return InterviewChatResponse(response=response)

    except Exception as e:
        logger.error(f"Interview chat error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to chat: {str(e)}",
        )
