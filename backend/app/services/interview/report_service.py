"""面试评估报告生成服务。"""

from __future__ import annotations

from collections.abc import AsyncIterator
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


@dataclass(frozen=True)
class InterviewReportProgressEvent:
    """用于承载报告生成 SSE 阶段状态。"""

    event_type: str
    phase: str
    label: str
    status: str
    progress: int
    result: InterviewReportResult | None = None

async def generate_interview_report(
    *, db: Session, user_id: int, session_id: int
) -> InterviewReportResult:
    """为已完成面试生成结构化评估报告。"""
    result: InterviewReportResult | None = None
    async for event in stream_interview_report(
        db=db, user_id=user_id, session_id=session_id
    ):
        if event.result is not None:
            result = event.result
    if result is None:
        raise ServiceError("Interview report generation ended without result")
    return result


async def stream_interview_report(
    *, db: Session, user_id: int, session_id: int
) -> AsyncIterator[InterviewReportProgressEvent]:
    """按真实后端步骤生成面试报告并产出进度事件。"""
    started_at = perf_counter()
    logger.info(
        "interview_report.requested",
        extra={"session_id": session_id, "user_id": user_id},
    )
    try:
        yield _report_phase("validate_session", "校验面试状态", "running", 5)
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
        yield _report_phase("validate_session", "校验面试状态", "completed", 12)

        yield _report_phase("load_turns", "读取面试回答", "running", 18)
        turns = _answered_turns(db, session_id)
        logger.info(
            "interview_report.turns_loaded",
            extra={
                "session_id": session_id,
                "user_id": user_id,
                "turn_count": len(turns),
            },
        )
        yield _report_phase("load_turns", "读取面试回答", "completed", 28)
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
            yield _report_phase(
                "done",
                "没有可复盘回答",
                "skipped",
                100,
                result=InterviewReportResult(session=session, generated=False),
            )
            return

        yield _report_phase("request_llm", "调用 AI 生成报告", "running", 36)
        response = await _request_report_response(session, turns)
        yield _report_phase("request_llm", "调用 AI 生成报告", "completed", 68)

        yield _report_phase("parse_report", "解析报告结构", "running", 74)
        report = _parse_report_response(response, turns)
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
        yield _report_phase("parse_report", "解析报告结构", "completed", 84)

        yield _report_phase("save_report", "保存报告结果", "running", 90)
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
        yield _report_phase("save_report", "保存报告结果", "completed", 100)
        yield _report_phase(
            "done",
            "报告已生成",
            "completed",
            100,
            result=InterviewReportResult(session=session, generated=True),
        )
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


def _report_phase(
    phase: str,
    label: str,
    status: str,
    progress: int,
    *,
    result: InterviewReportResult | None = None,
) -> InterviewReportProgressEvent:
    """构造报告生成阶段事件。"""
    return InterviewReportProgressEvent(
        event_type="done" if result is not None else "phase",
        phase=phase,
        label=label,
        status=status,
        progress=progress,
        result=result,
    )


def _answered_turns(db: Session, session_id: int) -> list[InterviewTurn]:
    """读取当前 session 中有回答内容的面试轮次。"""
    return (
        db.query(InterviewTurn)
        .filter(InterviewTurn.session_id == session_id)
        .filter(InterviewTurn.answer.isnot(None))
        .order_by(InterviewTurn.turn_index.asc())
        .all()
    )


async def _request_report_response(
    session: InterviewSession, turns: list[InterviewTurn]
) -> dict[str, Any]:
    """调用 LLM 生成面试报告原始响应。"""
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
                max_tokens=4500,
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
    return response


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
                "question_type": turn.question_type,
                "intent": turn.intent or "",
                "expected_points": turn.expected_points or [],
                "question": turn.question,
                "answer": turn.answer or "",
            }
            for turn in turns
        ],
    }


def _parse_report_response(
    response: dict[str, Any], turns: list[InterviewTurn]
) -> dict[str, Any]:
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
        logger.warning(
            "interview_report.invalid_json",
            extra={
                "response_chars": len(content),
                "json_error": str(exc),
            },
        )
        return _fallback_report_from_text(content, turns)
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
        "candidate_verdict": _candidate_verdict(report.get("candidate_verdict")),
        "job_match": _job_match(report.get("job_match")),
        "strengths": _string_list(report.get("strengths")),
        "weaknesses": _string_list(report.get("weaknesses")),
        "interviewer_risks": _string_list(report.get("interviewer_risks")),
        "next_training_plan": _string_list(report.get("next_training_plan")),
        "resume_feedback": _string_list(report.get("resume_feedback")),
        "answer_rewrites": _answer_rewrites(report.get("answer_rewrites")),
        "dimensions": _dimensions(report.get("dimensions")),
        "interviewer_evaluation": _interviewer_evaluation(report.get("interviewer_evaluation")),
        "learning_plan": _learning_plan(report.get("learning_plan")),
    }


def _learning_plan(value: Any) -> dict[str, Any]:
    """标准化学习规划字段。"""
    empty: dict[str, Any] = {"learning_priorities": [], "improvement_roadmap": []}
    if not isinstance(value, dict):
        return empty
    priorities = [
        {"topic": _as_text(item.get("topic")), "level": _as_text(item.get("level")) or "中"}
        for item in _list_of_dicts(value.get("learning_priorities"))
        if _as_text(item.get("topic"))
    ]
    roadmap = [
        {
            "phase": _as_text(item.get("phase")),
            "timeframe": _as_text(item.get("timeframe")),
            "items": _string_list(item.get("items")),
        }
        for item in _list_of_dicts(value.get("improvement_roadmap"))
        if _as_text(item.get("phase"))
    ]
    return {"learning_priorities": priorities, "improvement_roadmap": roadmap}


def _interviewer_evaluation(value: Any) -> dict[str, Any]:
    """标准化面试官综合评价字段。"""
    if not isinstance(value, dict):
        return {"overall": "", "key_observations": [], "core_recommendations": []}
    return {
        "overall": _as_text(value.get("overall")),
        "key_observations": _string_list(value.get("key_observations")),
        "core_recommendations": _string_list(value.get("core_recommendations")),
    }


def _dimensions(value: Any) -> list[dict[str, Any]]:
    """标准化报告维度列表。"""
    return [
        {
            "title": _as_text(item.get("title")),
            "score": _bounded_score(item.get("score")),
            "assessment": _as_text(item.get("assessment")),
            "evidence": _as_text(item.get("evidence")),
            "advice": _as_text(item.get("advice")),
        }
        for item in _list_of_dicts(value)
    ]


def _candidate_verdict(value: Any) -> dict[str, str]:
    """标准化候选人推进结论。"""
    if not isinstance(value, dict):
        return {"level": "", "label": "", "reason": ""}
    return {
        "level": _as_text(value.get("level")),
        "label": _as_text(value.get("label")),
        "reason": _as_text(value.get("reason")),
    }


def _job_match(value: Any) -> dict[str, Any]:
    """标准化岗位匹配判断。"""
    if not isinstance(value, dict):
        return {
            "target_title": "",
            "target_company": "",
            "required_capabilities": [],
            "covered_capabilities": [],
            "missing_capabilities": [],
            "interviewer_concerns": [],
            "likely_followups": [],
        }
    return {
        "target_title": _as_text(value.get("target_title")),
        "target_company": _as_text(value.get("target_company")),
        "required_capabilities": _string_list(value.get("required_capabilities")),
        "covered_capabilities": _string_list(value.get("covered_capabilities")),
        "missing_capabilities": _string_list(value.get("missing_capabilities")),
        "interviewer_concerns": _string_list(value.get("interviewer_concerns")),
        "likely_followups": _string_list(value.get("likely_followups")),
    }


def _answer_rewrites(value: Any) -> list[dict[str, Any]]:
    """标准化可直接复述的示范回答。"""
    rewrites: list[dict[str, Any]] = []
    for item in _list_of_dicts(value):
        rewrites.append(
            {
                "turn_index": _turn_index(item.get("turn_index")),
                "original_problem": _as_text(item.get("original_problem")),
                "recommended_answer": _as_text(item.get("recommended_answer")),
                "why_better": _as_text(item.get("why_better")),
            }
        )
    return rewrites


def _bounded_score(value: Any) -> int:
    """标准化 1 到 5 分的维度评分。"""
    if not isinstance(value, int):
        return 0
    return max(1, min(value, 5))


def _turn_index(value: Any) -> int | None:
    """标准化逐题关联的 turn_index。"""
    return value if isinstance(value, int) and value >= 0 else None


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


def _fallback_report_from_text(
    content: str, turns: list[InterviewTurn]
) -> dict[str, Any]:
    """在模型返回非严格 JSON 时生成可展示的保守报告。"""
    summary = " ".join(content.split())
    if len(summary) > 600:
        summary = f"{summary[:600]}..."
    if not summary:
        summary = "报告模型返回了非结构化内容，本次已保留面试记录用于后续复盘。"

    turn_evaluations = [
        {
            "turn_index": turn.turn_index,
            "summary": "已记录本轮问答，但模型返回的逐题点评格式不完整。",
            "gaps": ["需要重新生成报告以获得完整逐题点评"],
            "evidence": [],
            "advice": "补充量化结果、关键决策和个人贡献后再复盘。",
        }
        for turn in turns
    ]

    return {
        "summary": summary,
        "candidate_verdict": {
            "level": "risky",
            "label": "需要重新复盘",
            "reason": "模型没有返回可验证的结构化评估，当前只能基于已保存问答给出保守建议。",
        },
        "job_match": {
            "target_title": "",
            "target_company": "",
            "required_capabilities": [],
            "covered_capabilities": [],
            "missing_capabilities": ["结构化面试证据不足"],
            "interviewer_concerns": [
                "本次报告缺少完整维度分析，暂时无法可靠判断岗位匹配度。"
            ],
            "likely_followups": [
                "请重新生成报告后，再针对最弱回答准备追问。"
            ],
        },
        "strengths": [
            f"已完成 {len(turns)} 轮可复盘问答",
            "面试问题和回答已经保存",
            "候选人完成了本次面试流程",
        ],
        "weaknesses": [
            "本次模型返回的结构化格式不完整，详细维度需要重新生成",
        ],
        "interviewer_risks": [
            "面试官视角的核心风险尚未被可靠解析，需要重新生成结构化报告。",
        ],
        "next_training_plan": [
            "重新生成报告以获取完整结构化评估",
            "按 STAR 结构整理核心项目回答",
            "为每个项目补充量化结果和业务影响",
        ],
        "resume_feedback": [
            "将面试中提到的项目职责、技术栈和量化成果同步回简历。",
        ],
        "answer_rewrites": [
            {
                "turn_index": turns[0].turn_index if turns else None,
                "original_problem": "当前模型未能生成可靠示范回答。",
                "recommended_answer": "请先用 STAR 结构重写最核心项目：背景、你的职责、关键动作、量化结果。",
                "why_better": "该结构能先补足面试官最关心的职责边界和结果证据。",
            }
        ],
        "dimensions": [
            {
                "title": "报告完整性",
                "score": 1,
                "assessment": "需要重新生成",
                "evidence": "模型返回内容不是严格 JSON，系统已生成保守降级报告。",
                "advice": "重新点击生成报告，或减少单次面试内容后再生成。",
            }
        ],
        "learning_plan": {
            "learning_priorities": [
                {"topic": "面试结构化表达", "level": "高"},
                {"topic": "STAR法则训练", "level": "高"},
            ],
            "improvement_roadmap": [
                {
                    "phase": "立即行动",
                    "timeframe": "1-2周",
                    "items": ["重新生成完整报告获取个性化学习建议", "整理本次面试中每道题的回答要点"],
                },
            ],
        },
        "turn_evaluations": turn_evaluations,
    }


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
你是严谨、直接、以行动为导向的中文面试教练。报告目标不是打分，而是告诉用户下一次面试最该改哪几件事。
请从面试官视角判断候选人是否像目标岗位需要的人，并基于原始回答证据给出可执行建议。
请只返回 JSON，不要 Markdown。
JSON 字段必须包含：
- summary: 一句话结论，说明当前更像”可推进 / 边缘 / 风险较高”的哪一种
- candidate_verdict: 对象，包含 level/label/reason。level 可用 strong/borderline/risky
- job_match: 对象，包含 target_title/target_company/required_capabilities/covered_capabilities/missing_capabilities/interviewer_concerns/likely_followups
- strengths: 至少 3 条优势
- weaknesses: 至少 1 条改进点
- interviewer_risks: 至少 1 条面试官可能犹豫或追问的风险点
- next_training_plan: 至少 3 条训练建议
- resume_feedback: 至少 1 条简历反馈
- answer_rewrites: 数组，每项包含 turn_index/original_problem/recommended_answer/why_better。至少为最弱的 1 道题生成可直接复述的推荐回答
- dimensions: 数组，每项包含 title/score/assessment/evidence/advice。维度建议覆盖岗位相关度、技术深度、项目表达清晰度、证据/量化结果、沟通结构
- turn_evaluations: 数组，每项包含 turn_index/summary/gaps/evidence/advice
- interviewer_evaluation: 对象，包含：
  - overall: 3~5 句话的面试官总体评价，从面试官视角客观描述候选人整体表现
  - key_observations: 至少 4 条关键观察，描述候选人在面试中表现出的具体行为或模式（正负均可）
  - core_recommendations: 至少 4 条核心建议，给出候选人在下次面试或日常准备中最应该做的具体行动
- learning_plan: 对象，包含：
  - learning_priorities: 数组，每项包含 topic（技能/主题名称，简短，4-8字）和 level（”高”/”中”/”低”）。按优先级排序，至少 4 项
  - improvement_roadmap: 数组，固定 3 项（立即行动/短期目标/中期规划），每项包含：
    - phase: 固定为”立即行动”/”短期目标”/”中期规划”之一
    - timeframe: 时间范围，如”1-2周”/”1个月”/”2-3个月”
    - items: 该阶段具体可操作的任务，至少 3 条，每条20-60字，聚焦在候选人当前最弱的地方
所有判断必须基于输入中的 JD、问题和候选人回答。没有证据就写”未证明”，不要编造不存在的事实。
建议要具体到下次怎么说、怎么练、简历怎么补，不要写泛泛鼓励。
输出必须是一个紧凑 JSON 对象，不要代码块，不要解释文字，不要在字符串里使用未转义的双引号。
""".strip()
