"""
面试序列化服务模块

用于统一把面试模型转换成前端消费的响应结构。
"""

from __future__ import annotations

from typing import Any, Optional

from app.models import InterviewSession, InterviewTurn


def _normalize_string_list(value: Any) -> list[str]:
    """把列表中的项目转成去空白字符串列表。"""
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def serialize_turn_evaluation(evaluation: Any) -> Optional[dict[str, Any]]:
    """用于把 turn evaluation 统一转成结构化字典。"""
    if evaluation is None:
        return None
    if isinstance(evaluation, str):
        text = evaluation.strip()
        return {"summary": text, "gaps": [], "evidence": [], "advice": ""} if text else None
    if isinstance(evaluation, dict):
        return {
            "summary": str(evaluation.get("summary") or "").strip(),
            "gaps": _normalize_string_list(evaluation.get("gaps")),
            "evidence": _normalize_string_list(evaluation.get("evidence")),
            "advice": str(evaluation.get("advice") or "").strip(),
        }
    return None


def serialize_turn(turn: InterviewTurn) -> dict[str, Any]:
    """用于把面试轮次对象转换成响应字典。"""
    return {
        "id": turn.id,
        "turn_index": turn.turn_index,
        "round_index": turn.round_index,
        "question": turn.question,
        "question_type": turn.question_type,
        "intent": turn.intent,
        "expected_points": turn.expected_points,
        "answer": turn.answer,
        "evaluation": serialize_turn_evaluation(turn.evaluation),
        "follow_up_count": turn.follow_up_count,
        "status": turn.status,
        "asked_at": turn.asked_at.isoformat() if turn.asked_at else None,
        "answered_at": turn.answered_at.isoformat() if turn.answered_at else None,
    }


def latest_turn(session: InterviewSession) -> Optional[InterviewTurn]:
    """用于获取当前 session 最新的一轮提问。"""
    turns = list(session.turns or [])
    return turns[-1] if turns else None


def serialize_session(session: InterviewSession) -> dict[str, Any]:
    """用于把完整面试 session 转成前端可消费结构。"""
    turns = list(session.turns or [])
    return {
        "id": session.id,
        "resume_id": session.resume_id,
        "target_title": session.target_title,
        "target_company": session.target_company,
        "jd_text": session.jd_text,
        "interview_type": session.interview_type,
        "difficulty": session.difficulty,
        "language": session.language,
        "mode": session.mode,
        "status": session.status,
        "current_round_index": session.current_round_index,
        "current_turn_index": session.current_turn_index,
        "plan": session.plan_json,
        "report_data": session.report_data,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        "turns": [serialize_turn(turn) for turn in turns],
        "current_turn": serialize_turn(turns[-1]) if turns else None,
    }


def serialize_session_summary(
    session: InterviewSession,
    *,
    answered_turn_count: int = 0,
) -> dict[str, Any]:
    """用于把面试 session 转成列表页摘要结构。"""
    return {
        "id": session.id,
        "resume_id": session.resume_id,
        "target_title": session.target_title,
        "target_company": session.target_company,
        "jd_text": session.jd_text,
        "interview_type": session.interview_type,
        "difficulty": session.difficulty,
        "language": session.language,
        "mode": session.mode,
        "status": session.status,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        "answered_turn_count": answered_turn_count,
        "has_report": bool(session.report_data),
    }
