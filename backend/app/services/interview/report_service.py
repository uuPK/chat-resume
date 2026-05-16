"""面试评估报告生成服务。"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from sqlalchemy.orm import Session

from app.models import InterviewSession, InterviewTurn
from app.services.errors import ServiceError, ServiceValidationError
from app.services.interview.session_service import get_session_for_user
from app.services.llm import ChatService

logger = logging.getLogger(__name__)


@dataclass
class InterviewReportResult:
    """用于承载报告生成后的 session 和动作状态。"""

    session: InterviewSession
    generated: bool


async def generate_interview_report(
    *, db: Session, user_id: int, session_id: int
) -> InterviewReportResult:
    """为已完成面试生成结构化评估报告。"""
    started_at = perf_counter()
    logger.info(
        "interview_report.requested",
        extra={"session_id": session_id, "user_id": user_id},
    )
    try:
        session = get_session_for_user(db, session_id, user_id)
        if session.status != "completed":
            logger.warning(
                "interview_report.invalid_status",
                extra={
                    "session_id": session_id,
                    "user_id": user_id,
                    "interview_status": session.status,
                },
            )
            raise ServiceValidationError(
                "Interview must be completed before generating report"
            )

        turns = _answered_turns(db, session_id)
        logger.info(
            "interview_report.turns_loaded",
            extra={
                "session_id": session_id,
                "user_id": user_id,
                "turn_count": len(turns),
            },
        )
        if not turns:
            logger.info(
                "interview_report.skipped",
                extra={
                    "session_id": session_id,
                    "user_id": user_id,
                    "reason": "no_answered_turns",
                    "elapsed_ms": _elapsed_ms(started_at),
                },
            )
            return InterviewReportResult(session=session, generated=False)

        report = await _request_report_from_llm(session, turns)
        public_report = _public_report(report)
        turn_evaluation_count = _apply_turn_evaluations(turns, report)
        logger.info(
            "interview_report.parsed",
            extra={
                "session_id": session_id,
                "user_id": user_id,
                "strength_count": len(public_report["strengths"]),
                "dimension_count": len(public_report["dimensions"]),
                "turn_evaluation_count": turn_evaluation_count,
            },
        )
        session.report_data = public_report
        db.commit()
        db.refresh(session)
        logger.info(
            "interview_report.saved",
            extra={
                "session_id": session_id,
                "user_id": user_id,
                "turn_evaluation_count": turn_evaluation_count,
                "elapsed_ms": _elapsed_ms(started_at),
            },
        )
        return InterviewReportResult(session=session, generated=True)
    except ServiceValidationError:
        raise
    except Exception:
        logger.exception(
            "interview_report.failed",
            extra={
                "session_id": session_id,
                "user_id": user_id,
                "elapsed_ms": _elapsed_ms(started_at),
            },
        )
        raise


def _answered_turns(db: Session, session_id: int) -> list[InterviewTurn]:
    """读取当前 session 中有回答内容的面试轮次。"""
    return (
        db.query(InterviewTurn)
        .filter(InterviewTurn.session_id == session_id)
        .filter(InterviewTurn.answer.isnot(None))
        .order_by(InterviewTurn.turn_index.asc())
        .all()
    )


async def _request_report_from_llm(
    session: InterviewSession, turns: list[InterviewTurn]
) -> dict[str, Any]:
    """调用 LLM 生成面试报告 JSON。"""
    payload = _report_prompt_payload(session, turns)
    prompt_chars = len(json.dumps(payload, ensure_ascii=False))
    llm_started_at = perf_counter()
    try:
        async with ChatService() as chat_service:
            logger.info(
                "interview_report.llm.started",
                extra={
                    "session_id": session.id,
                    "model": getattr(chat_service, "model", "unknown"),
                    "turn_count": len(turns),
                    "prompt_chars": prompt_chars,
                },
            )
            response = await chat_service.chat_completion(
                messages=[
                    {
                        "role": "user",
                        "content": json.dumps(payload, ensure_ascii=False),
                    }
                ],
                temperature=0.2,
                max_tokens=1800,
                system_prompt=_REPORT_SYSTEM_PROMPT,
            )
    except Exception as exc:
        raise ServiceError(f"Interview report generation failed: {exc}") from exc

    response_chars = _response_content_length(response)
    logger.info(
        "interview_report.llm.completed",
        extra={
            "session_id": session.id,
            "turn_count": len(turns),
            "elapsed_ms": _elapsed_ms(llm_started_at),
            "response_chars": response_chars,
        },
    )
    return _parse_report_response(response)


def _report_prompt_payload(
    session: InterviewSession, turns: list[InterviewTurn]
) -> dict[str, Any]:
    """构造面试报告生成所需的输入上下文。"""
    return {
        "target_title": session.target_title or "",
        "target_company": session.target_company or "",
        "jd_text": session.jd_text or "",
        "language": session.language,
        "turns": [
            {
                "turn_index": turn.turn_index,
                "question": turn.question,
                "answer": turn.answer or "",
            }
            for turn in turns
        ],
    }


def _parse_report_response(response: dict[str, Any]) -> dict[str, Any]:
    """从 OpenRouter 响应中解析结构化报告 JSON。"""
    content = (
        response.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )
    if not isinstance(content, str) or not content.strip():
        raise ServiceError("Interview report generation returned empty content")

    try:
        parsed = json.loads(_extract_json_object(content))
    except json.JSONDecodeError as exc:
        raise ServiceError("Interview report generation returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise ServiceError("Interview report generation returned non-object JSON")
    return parsed


def _extract_json_object(content: str) -> str:
    """提取模型回复中的首个 JSON 对象文本。"""
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        stripped = stripped.removeprefix("json").strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start < 0 or end <= start:
        return stripped
    return stripped[start : end + 1]


def _apply_turn_evaluations(
    turns: list[InterviewTurn], report: dict[str, Any]
) -> int:
    """把报告中的逐题点评写回对应 turn。"""
    by_index = {turn.turn_index: turn for turn in turns}
    applied_count = 0
    for item in _list_of_dicts(report.get("turn_evaluations")):
        turn_index = item.get("turn_index")
        if not isinstance(turn_index, int) or turn_index not in by_index:
            continue
        by_index[turn_index].evaluation = {
            "summary": _as_text(item.get("summary")),
            "gaps": _string_list(item.get("gaps")),
            "evidence": _string_list(item.get("evidence")),
            "advice": _as_text(item.get("advice")),
        }
        applied_count += 1
    return applied_count


def _public_report(report: dict[str, Any]) -> dict[str, Any]:
    """整理前端可展示的报告字段。"""
    return {
        "summary": _as_text(report.get("summary")),
        "strengths": _string_list(report.get("strengths")),
        "weaknesses": _string_list(report.get("weaknesses")),
        "next_training_plan": _string_list(report.get("next_training_plan")),
        "resume_feedback": _string_list(report.get("resume_feedback")),
        "dimensions": _dimensions(report.get("dimensions")),
    }


def _dimensions(value: Any) -> list[dict[str, str]]:
    """标准化报告维度列表。"""
    return [
        {
            "title": _as_text(item.get("title")),
            "assessment": _as_text(item.get("assessment")),
            "evidence": _as_text(item.get("evidence")),
            "advice": _as_text(item.get("advice")),
        }
        for item in _list_of_dicts(value)
    ]


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    """过滤出字典列表。"""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _string_list(value: Any) -> list[str]:
    """标准化字符串列表。"""
    if not isinstance(value, list):
        return []
    return [text for text in (_as_text(item) for item in value) if text]


def _as_text(value: Any) -> str:
    """把任意值转为去空白字符串。"""
    return value.strip() if isinstance(value, str) else ""


def _response_content_length(response: dict[str, Any]) -> int:
    """计算模型响应正文长度，不记录正文内容。"""
    content = (
        response.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )
    return len(content) if isinstance(content, str) else 0


def _elapsed_ms(started_at: float) -> float:
    """计算从指定时间点开始的毫秒耗时。"""
    return round((perf_counter() - started_at) * 1000, 2)


_REPORT_SYSTEM_PROMPT = """
你是严谨的中文面试评估专家。请只返回 JSON，不要 Markdown。
JSON 字段必须包含：
- summary: 整体总结
- strengths: 至少 3 条优势
- weaknesses: 至少 1 条改进点
- next_training_plan: 至少 3 条训练建议
- resume_feedback: 至少 1 条简历反馈
- dimensions: 数组，每项包含 title/assessment/evidence/advice
- turn_evaluations: 数组，每项包含 turn_index/summary/gaps/evidence/advice
逐题点评必须基于输入中的问题和候选人回答，不要编造不存在的事实。
""".strip()
