"""
结构化面试 API

提供面试 session / turn 的最小闭环接口。
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from uuid import uuid4

logger = logging.getLogger(__name__)
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import case, func
from sqlalchemy.orm import Session, noload

from app.entrypoints.http.deps import get_current_user
from app.agents.interview import InterviewerAgent
from app.infra.database import get_db
from app.infra.langfuse_observer import LangfuseRunObserver
from app.infra.request_context import log_context
from app.models import InterviewSession, InterviewTurn
from app.schemas.resume import dump_resume_content_for_frontend
from app.services.domain import ResumeService

router = APIRouter()

_interviewer_agent = InterviewerAgent()


def _now() -> datetime:
    """用于统一生成带时区的当前时间。"""
    return datetime.now(timezone.utc)


def _get_resume_for_user(db: Session, resume_id: int, user_id: int):
    """用于校验用户对目标简历的访问权限。"""
    resume = ResumeService(db).get_by_id(resume_id)
    if not resume:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    if resume.owner_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    return resume


_ROUND_INSTRUCTIONS: dict[str, str] = {
    "warmup": (
        "【当前阶段：热身】"
        "目标是建立基本画像、确认岗位匹配度。"
        "只问自我介绍、求职动机、近期状态等开放性问题。"
        "不要追技术细节，不要追项目数字，不要出行为题。"
        "语气可以稍微轻松，帮候选人热身。"
    ),
    "resume_deep_dive": (
        "【当前阶段：项目深挖】"
        "目标是验证简历真实性，挖出候选人的真实贡献和量化结果。"
        "紧盯简历里的具体项目或工作经历，逐一追问：你具体做了什么、遇到了什么困难、最终结果是什么数字。"
        "如果候选人回答空泛，必须追问：个人贡献是什么、结果怎么量化、是怎么解决问题的。"
        "不要转移到和简历无关的话题。"
    ),
    "behavioral": (
        "【当前阶段：行为面试】"
        "目标是考察软技能，要求候选人用 STAR 结构（情境、任务、行动、结果）回答。"
        "典型问题：团队冲突经历、失败项目的处理、跨部门协作、在压力下的决策。"
        "如果回答缺少结果或个人行动，必须追问最终结果和复盘结论。"
        "不要出纯技术题。"
    ),
    "technical": (
        "【当前阶段：技术考察】"
        "目标是考察技术深度、工程判断和系统思维。"
        "可以问架构设计、技术选型理由、性能优化、线上排障经历、代码质量等。"
        "如果候选人给出结论，必须追问：为什么这样选、有什么取舍、遇到了什么坑。"
        "不要问纯行为或软技能问题。"
    ),
    "closing": (
        "【当前阶段：收尾】"
        "目标是给候选人反问机会，并做简短的面试收尾。"
        "可以问：你对这个岗位或团队有什么想了解的？你觉得自己最大的短板是什么？"
        "不要出新的技术题或行为题。语气回归轻松，给候选人一个好的结束体验。"
    ),
}


def _round_instructions(question_type: str) -> str:
    """用于按面试阶段返回固定提问约束。"""
    return _ROUND_INSTRUCTIONS.get(question_type, "")


def _build_first_round_prompt(question_type: str, round_goal: str) -> str:
    """用于生成首轮提问时的系统提示。"""
    instructions = _round_instructions(question_type)
    return f"{instructions}\n开始一场模拟面试。当前阶段目标：{round_goal}。请直接提出第一题。"


def _build_next_round_prompt(question_type: str, round_goal: str) -> str:
    """用于生成切换到下一轮时的提问提示。"""
    instructions = _round_instructions(question_type)
    return f"{instructions}\n进入下一阶段：{round_goal}。请直接提出该阶段的第一个问题。"


def _build_same_round_prompt(question_type: str, round_goal: str, remaining_questions: int) -> str:
    """用于生成同一轮内继续追问时的提问提示。"""
    instructions = _round_instructions(question_type)
    return (
        f"{instructions}\n当前面试阶段：{round_goal}（本阶段还可再问 {remaining_questions} 题）。"
        "根据候选人刚才的回答，决定追问细节还是转向该阶段下一个核心问题。"
    )


def _build_hint_prompt(
    *,
    question_type: str,
    question: str,
    round_goal: str,
    target_title: str,
) -> str:
    """用于生成练习模式下的答题提示词。"""
    instructions = _round_instructions(question_type)
    role_hint = f"目标岗位：{target_title}。" if target_title else ""
    return (
        f"{instructions}\n"
        f"{role_hint}"
        f"当前问题：{question}\n"
        f"当前阶段目标：{round_goal}\n"
        "请给候选人 3 条简短提示，帮助其组织答案。"
        "每条提示都要可执行，聚焦回答结构、关键信息和量化结果。"
        "不要直接替候选人写完整答案。"
    )


def _rounds_for_type(interview_type: str) -> list[dict[str, Any]]:
    """用于根据面试类型生成默认轮次规划。"""
    if interview_type == "behavioral":
        return [
            {"type": "warmup", "goal": "自我介绍与背景确认", "max_questions": 2},
            {"type": "behavioral", "goal": "行为事件与协作能力", "max_questions": 4},
            {"type": "behavioral", "goal": "冲突处理与复盘能力", "max_questions": 3},
            {"type": "closing", "goal": "总结与反问", "max_questions": 2},
        ]
    if interview_type == "technical":
        return [
            {"type": "warmup", "goal": "自我介绍与岗位匹配", "max_questions": 2},
            {"type": "resume_deep_dive", "goal": "项目真实性与个人贡献", "max_questions": 4},
            {"type": "technical", "goal": "技术深度与工程判断", "max_questions": 4},
            {"type": "technical", "goal": "系统设计与排障能力", "max_questions": 3},
            {"type": "closing", "goal": "总结与反问", "max_questions": 2},
        ]
    return [
        {"type": "warmup", "goal": "自我介绍与背景确认", "max_questions": 2},
        {"type": "resume_deep_dive", "goal": "项目深挖与个人贡献", "max_questions": 15},
        {"type": "behavioral", "goal": "行为能力与沟通协作", "max_questions": 3},
        {"type": "closing", "goal": "总结与反问", "max_questions": 2},
    ]


def _build_plan(resume_content: dict[str, Any], interview_type: str) -> dict[str, Any]:
    """用于构建一场结构化面试的初始计划。"""
    resume_content = dump_resume_content_for_frontend(resume_content or {})
    return {
        "rounds": _rounds_for_type(interview_type),
        "resume_highlights": {
            "work_experience_count": len(resume_content.get("work_experience") or []),
            "project_count": len(resume_content.get("projects") or []),
            "target_title": ((resume_content.get("job_application") or {}).get("target_title") or ""),
            "target_company": ((resume_content.get("job_application") or {}).get("target_company") or ""),
        },
    }


def _serialize_turn(turn: InterviewTurn) -> dict[str, Any]:
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
        "evaluation": _normalize_evaluation_text(turn.evaluation),
        "follow_up_count": turn.follow_up_count,
        "status": turn.status,
        "asked_at": turn.asked_at.isoformat() if turn.asked_at else None,
        "answered_at": turn.answered_at.isoformat() if turn.answered_at else None,
    }


def _serialize_session(session: InterviewSession) -> dict[str, Any]:
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
        "turns": [_serialize_turn(turn) for turn in turns],
        "current_turn": _serialize_turn(turns[-1]) if turns else None,
    }


def _serialize_session_summary(
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
        "interview_type": session.interview_type,
        "difficulty": session.difficulty,
        "language": session.language,
        "mode": session.mode,
        "status": session.status,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        "answered_turn_count": answered_turn_count,
    }


def _latest_turn(session: InterviewSession) -> Optional[InterviewTurn]:
    """用于获取当前 session 最新的一轮提问。"""
    turns = list(session.turns or [])
    return turns[-1] if turns else None


def _collect_weaknesses(turns: list[InterviewTurn]) -> list[str]:
    """用于在没有结构化评分后生成通用的改进建议。"""
    if any(_normalize_evaluation_text(turn.evaluation) for turn in turns):
        return [
            "逐题复盘面试评语，优先补足背景、动作和结果。",
            "围绕个人贡献和量化结果重新打磨回答。",
        ]
    return []


def _normalize_evaluation_text(evaluation: Any) -> str:
    """用于把历史结构化评估和新文本评估统一转换成纯文本。"""
    if isinstance(evaluation, str):
        return evaluation.strip()
    if not isinstance(evaluation, dict):
        return ""

    parts: list[str] = []
    summary = str(evaluation.get("summary") or "").strip()
    if summary:
        parts.append(summary)

    gaps = [str(item).strip() for item in (evaluation.get("gaps") or []) if str(item).strip()]
    if gaps:
        parts.append("问题：" + "；".join(gaps[:3]))

    evidence = [str(item).strip() for item in (evaluation.get("evidence") or []) if str(item).strip()]
    if evidence:
        parts.append("亮点：" + "；".join(evidence[:2]))

    return "\n".join(parts).strip()


def _fallback_hint(turn: InterviewTurn) -> list[str]:
    """用于在提示生成失败时返回可直接使用的练习建议。"""
    tips = [
        "先交代背景和目标，再说明你亲自做了什么。",
        "一定讲出结果，最好补一到两个量化指标。",
        "把重点放在个人贡献和关键决策，不要只讲团队工作。",
    ]
    if turn.question_type == "behavioral":
        tips = [
            "按 STAR 结构回答：情境、任务、行动、结果。",
            "重点讲你本人采取了什么行动，不要只描述团队。",
            "最后补一句复盘，说明你从这件事里学到了什么。",
        ]
    elif turn.question_type == "technical":
        tips = [
            "先给结论，再说明为什么这样设计或选择。",
            "补充技术取舍、风险和你如何验证方案有效。",
            "最好举一个线上问题、性能指标或工程细节来支撑答案。",
        ]
    return tips




async def _generate_question(
    *,
    resume_content: dict[str, Any],
    history: list[dict[str, str]],
    prompt: str,
    event_callback=None,
) -> str:
    """用于调用面试 Agent 生成下一道问题。"""
    result = await _interviewer_agent.chat(
        user_message=prompt,
        resume_content=resume_content,
        conversation_history=history,
        event_callback=event_callback,
    )
    return (result.get("content") or "").strip()


def _fallback_evaluation(question: str, answer: str) -> str:
    """用于在 LLM 评估失败时提供简短文本兜底结果。"""
    normalized = (answer or "").strip()
    gaps: list[str] = []
    missing_question_focus = False
    question_keywords = re.findall(r"[\u4e00-\u9fffA-Za-z]{2,}", question or "")
    if question_keywords and not any(keyword in normalized for keyword in question_keywords[:4]):
        missing_question_focus = True
    if len(normalized) < 60:
        gaps.append("回答偏短，缺少背景和结果")
    if "我" not in normalized:
        gaps.append("个人贡献不够明确")
    if not any(ch.isdigit() for ch in normalized):
        gaps.append("缺少量化结果或具体指标")
    if missing_question_focus:
        gaps.insert(0, "没有直接回应问题本身")
    if gaps:
        return "面试系统反馈：" + "；".join(gaps[:2]) + "。建议先直接回答问题，再补充个人贡献和结果。"
    return "面试系统反馈：回答基本切题，但还可以补充更具体的个人动作和结果，让信息更完整。"


async def _evaluate_answer_with_llm(
    *,
    question: str,
    answer: str,
    resume_content: dict[str, Any],
    history: list[dict[str, str]],
    event_callback=None,
) -> str:
    """用于让 LLM 对候选人回答做文本评估。"""
    prompt = (
        f"[EVALUATE]\n"
        f"面试问题：{question}\n"
        f"候选人回答：{answer}\n"
        "请从面试系统的角度给出简短反馈，不要使用面试官训话口吻。"
        "先指出是否答到问题本身，再指出最关键的缺口，并给一个最重要的补强建议。"
        "长度控制在 1 到 2 句话。"
    )
    try:
        result = await _interviewer_agent.chat(
            user_message=prompt,
            resume_content=resume_content,
            conversation_history=history,
            event_callback=event_callback,
        )
        raw = (result.get("content") or "").strip()
        if raw:
            return raw
        return _fallback_evaluation(question, answer)
    except Exception:
        logger.warning("LLM evaluation failed, falling back to rule-based evaluation")
        return _fallback_evaluation(question, answer)


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
    evaluation: Optional[Dict[str, Any]] = None
    next_action: Optional[str] = None


@router.post("/", response_model=InterviewActionResponse)
async def create_interview(
    request: InterviewCreateRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于创建一场新的结构化模拟面试。"""
    resume = _get_resume_for_user(db, request.resume_id, current_user["id"])
    resume_content = resume.content if isinstance(resume.content, dict) else {}
    plan = _build_plan(resume_content, request.interview_type)
    job_application = (resume_content.get("job_application") or {}) if isinstance(resume_content, dict) else {}

    session = InterviewSession(
        user_id=current_user["id"],
        resume_id=request.resume_id,
        target_title=request.target_title or str(job_application.get("target_title", "") or ""),
        target_company=request.target_company or str(job_application.get("target_company", "") or ""),
        jd_text=request.jd_text or str(job_application.get("jd_text", "") or ""),
        interview_type=request.interview_type,
        difficulty=request.difficulty,
        language=request.language,
        mode=request.mode,
        status="interview_ready",
        current_round_index=0,
        current_turn_index=0,
        plan_json=plan,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return InterviewActionResponse(session=_serialize_session(session), next_action="start")


@router.post("/{session_id}/hint", response_model=InterviewHintResponse)
async def get_interview_hint(
    session_id: int,
    http_request: Request,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于在练习模式下为当前题目生成简短提示。"""
    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session or session.user_id != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found")
    if session.mode != "practice":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Hints are only available in practice mode")

    turn = _latest_turn(session)
    if not turn or turn.status != "asked":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No active question to hint")

    resume = _get_resume_for_user(db, session.resume_id, current_user["id"])
    resume_content = resume.content if isinstance(resume.content, dict) else {}
    history: list[dict[str, str]] = []
    for item in list(session.turns or []):
        history.append({"role": "assistant", "content": item.question})
        if item.answer:
            history.append({"role": "user", "content": item.answer})

    run_id = uuid4().hex
    observer = LangfuseRunObserver(
        run_id=run_id,
        agent_type="interview",
        run_kind="hint_interview",
        user_id=current_user["id"],
        input_text=turn.question,
        metadata={
            "interview_session_id": session.id,
            "resume_id": session.resume_id,
            "request_id": getattr(http_request.state, "request_id", None),
        },
    )
    prompt = _build_hint_prompt(
        question_type=turn.question_type,
        question=turn.question,
        round_goal=turn.intent or "",
        target_title=session.target_title or "",
    )
    hints = _fallback_hint(turn)
    try:
        with observer:
            result = await _interviewer_agent.chat(
                user_message=prompt,
                resume_content=resume_content,
                conversation_history=history,
                event_callback=observer.on_runtime_event,
            )
        raw = (result.get("content") or "").strip()
        parsed = [
            re.sub(r"^\s*(?:[-*•]|\d+[.)、])\s*", "", line).strip()
            for line in raw.splitlines()
            if line.strip()
        ]
        if parsed:
            hints = parsed[:3]
        observer.finish("hint_generated")
    except Exception as exc:
        observer.fail(str(exc))
        logger.warning("Hint generation failed, falling back to default hints")
    return InterviewHintResponse(hints=hints)


@router.get("/", response_model=List[Dict[str, Any]])
async def list_interviews(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于返回当前用户的面试 session 列表。"""
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
            func.coalesce(answered_turn_counts.c.answered_turn_count, 0).label("answered_turn_count"),
        )
        .outerjoin(answered_turn_counts, answered_turn_counts.c.session_id == InterviewSession.id)
        .options(noload(InterviewSession.turns))
        .filter(InterviewSession.user_id == current_user["id"])
        .order_by(InterviewSession.id.desc())
        .all()
    )
    return [
        _serialize_session_summary(session, answered_turn_count=int(answered_turn_count or 0))
        for session, answered_turn_count in sessions
    ]


@router.get("/{session_id}", response_model=InterviewActionResponse)
async def get_interview(
    session_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于返回单场面试的完整状态。"""
    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session or session.user_id != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found")
    return InterviewActionResponse(session=_serialize_session(session))


@router.post("/{session_id}/start", response_model=InterviewActionResponse)
async def start_interview(
    session_id: int,
    http_request: Request,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于启动一场待开始的面试并生成第一题。"""
    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session or session.user_id != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found")
    if session.status not in {"created", "interview_ready"}:
        return InterviewActionResponse(session=_serialize_session(session))

    resume = _get_resume_for_user(db, session.resume_id, current_user["id"])
    resume_content = resume.content if isinstance(resume.content, dict) else {}
    run_id = uuid4().hex
    observer = LangfuseRunObserver(
        run_id=run_id,
        agent_type="interview",
        run_kind="start_interview",
        user_id=current_user["id"],
        input_text="开始模拟面试并生成第一题",
        metadata={
            "interview_session_id": session.id,
            "resume_id": session.resume_id,
            "request_id": getattr(http_request.state, "request_id", None),
        },
    )
    rounds = ((session.plan_json or {}).get("rounds") or [])
    first_round = rounds[0] if rounds else {}
    round_goal = first_round.get("goal", "自我介绍与岗位匹配")
    try:
        with observer:
            question = await _generate_question(
                resume_content=resume_content,
                history=[],
                prompt=_build_first_round_prompt(first_round.get("type", "warmup"), round_goal),
                event_callback=observer.on_runtime_event,
            )
    except Exception as exc:
        observer.fail(str(exc))
        raise
    if not question:
        question = "先用两分钟做一个和目标岗位最相关的自我介绍。"

    turn = InterviewTurn(
        session_id=session.id,
        turn_index=1,
        round_index=0,
        question=question,
        question_type=rounds[0]["type"] if rounds else "warmup",
        intent=round_goal,
        status="asked",
        asked_at=_now(),
    )
    session.status = "waiting_user_answer"
    session.current_turn_index = 1
    session.started_at = session.started_at or _now()
    db.add(turn)
    db.commit()
    db.refresh(session)
    observer.finish(question)
    return InterviewActionResponse(
        session=_serialize_session(session),
        message=question,
        next_action="answer",
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
    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session or session.user_id != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found")
    if session.status == "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Interview already completed")

    turn = _latest_turn(session)
    if not turn or turn.status != "asked":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No active question to answer")

    answer_text = request.answer.strip()

    resume = _get_resume_for_user(db, session.resume_id, current_user["id"])
    resume_content = resume.content if isinstance(resume.content, dict) else {}
    run_id = uuid4().hex
    observer = LangfuseRunObserver(
        run_id=run_id,
        agent_type="interview",
        run_kind="answer_interview",
        user_id=current_user["id"],
        input_text=answer_text,
        metadata={
            "interview_session_id": session.id,
            "resume_id": session.resume_id,
            "request_id": getattr(http_request.state, "request_id", None),
        },
    )
    history: list[dict[str, str]] = []
    for item in list(session.turns or []):
        history.append({"role": "assistant", "content": item.question})
        if item.answer and item is not turn:
            history.append({"role": "user", "content": item.answer})
    # 将当前回答加入历史，让 LLM 基于最新回答生成下一题
    history.append({"role": "user", "content": answer_text})

    turn.answer = answer_text
    turn.answered_at = _now()
    turn.status = "done"
    turn.evaluation = await _evaluate_answer_with_llm(
        question=turn.question,
        answer=answer_text,
        resume_content=resume_content,
        history=history,
        event_callback=observer.on_runtime_event,
    )

    rounds = ((session.plan_json or {}).get("rounds") or [])
    current_round = rounds[turn.round_index] if turn.round_index < len(rounds) else {}
    max_q = int(current_round.get("max_questions") or 2)
    questions_in_round = sum(1 for t in session.turns if t.round_index == turn.round_index)
    force_next_round = questions_in_round >= max_q

    if force_next_round:
        next_round_index = turn.round_index + 1
    else:
        next_round_index = turn.round_index

    if force_next_round and next_round_index >= len(rounds):
        session.status = "completed"
        session.ended_at = _now()
        session.report_data = {
            "summary": "本场模拟面试已结束。",
            "strengths": ["能持续回答问题并完成整场面试。"],
            "weaknesses": _collect_weaknesses(list(session.turns or [])),
            "next_training_plan": [
                "每个回答都补足背景、动作、结果。",
                "突出个人贡献，避免只讲团队。",
                "尽量加入量化指标和复盘结论。",
            ],
        }
        db.commit()
        db.refresh(session)
        observer.finish("interview_completed")
        return InterviewActionResponse(
            session=_serialize_session(session),
            next_action="completed",
        )

    if force_next_round:
        next_round = rounds[next_round_index]
        prompt = _build_next_round_prompt(next_round["type"], next_round["goal"])
        new_round_index = next_round_index
        new_round_type = next_round["type"]
        new_round_goal = next_round["goal"]
    else:
        remaining = max_q - questions_in_round
        prompt = _build_same_round_prompt(current_round["type"], current_round["goal"], remaining)
        new_round_index = turn.round_index
        new_round_type = current_round["type"]
        new_round_goal = current_round["goal"]

    try:
        with observer:
            question = await _generate_question(
                resume_content=resume_content,
                history=history,
                prompt=prompt,
                event_callback=observer.on_runtime_event,
            )
    except Exception as exc:
        observer.fail(str(exc))
        raise
    if not question:
        question = "挑一个你最能代表岗位匹配度的项目，讲清楚背景、目标、你的动作和结果。"
    next_turn = InterviewTurn(
        session_id=session.id,
        turn_index=session.current_turn_index + 1,
        round_index=new_round_index,
        question=question,
        question_type=new_round_type,
        intent=new_round_goal,
        status="asked",
        asked_at=_now(),
    )
    session.current_turn_index += 1
    session.current_round_index = new_round_index
    session.status = "waiting_user_answer"
    db.add(next_turn)
    db.commit()
    db.refresh(session)
    observer.finish(question)
    return InterviewActionResponse(
        session=_serialize_session(session),
        message=question,
        next_action="next_question",
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
    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session or session.user_id != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found")
    if session.status == "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Interview already completed")

    turn = _latest_turn(session)
    if not turn or turn.status != "asked":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No active question to answer")

    answer_text = request.answer.strip()
    resume = _get_resume_for_user(db, session.resume_id, current_user["id"])
    resume_content = resume.content if isinstance(resume.content, dict) else {}
    run_id = uuid4().hex
    observer = LangfuseRunObserver(
        run_id=run_id,
        agent_type="interview",
        run_kind="answer_interview_stream",
        user_id=current_user["id"],
        input_text=answer_text,
        metadata={
            "interview_session_id": session.id,
            "resume_id": session.resume_id,
            "request_id": getattr(http_request.state, "request_id", None),
        },
    )

    history: list[dict[str, str]] = []
    for item in list(session.turns or []):
        history.append({"role": "assistant", "content": item.question})
        if item.answer and item is not turn:
            history.append({"role": "user", "content": item.answer})
    # 将当前回答加入历史，让 LLM 基于最新回答生成下一题
    history.append({"role": "user", "content": answer_text})

    turn.answer = answer_text
    turn.answered_at = _now()
    turn.status = "done"
    turn.evaluation = await _evaluate_answer_with_llm(
        question=turn.question,
        answer=answer_text,
        resume_content=resume_content,
        history=history,
        event_callback=observer.on_runtime_event,
    )

    async def generate():
        nonlocal session
        with log_context(
            request_id=getattr(http_request.state, "request_id", None),
            session_id=str(session_id),
        ):
            logger.info("Interview stream started")
            with observer:
                rounds = ((session.plan_json or {}).get("rounds") or [])
                current_round = rounds[turn.round_index] if turn.round_index < len(rounds) else {}
                max_q = int(current_round.get("max_questions") or 2)
                questions_in_round = sum(1 for t in session.turns if t.round_index == turn.round_index)
                force_next_round = questions_in_round >= max_q

                if force_next_round:
                    next_round_index = turn.round_index + 1
                else:
                    next_round_index = turn.round_index

                is_completed = force_next_round and next_round_index >= len(rounds)

                # 1. 决定 prompt
                if is_completed:
                    prompt = None
                elif force_next_round:
                    next_round = rounds[next_round_index]
                    prompt = _build_next_round_prompt(next_round["type"], next_round["goal"])
                else:
                    remaining = max_q - questions_in_round
                    prompt = _build_same_round_prompt(current_round["type"], current_round["goal"], remaining)

                # 2. 流式生成问题（结束场景跳过）
                accumulated = ""
                if prompt is not None:
                    try:
                        async for chunk in _interviewer_agent.chat_stream(
                            user_message=prompt,
                            resume_content=resume_content,
                            conversation_history=history,
                            event_callback=observer.on_runtime_event,
                        ):
                            token = chunk.get("content") or ""
                            if token:
                                accumulated += token
                                yield f"data: {json.dumps({'type': 'token', 'content': token}, ensure_ascii=False)}\n\n"
                    except Exception as e:
                        observer.fail(str(e))
                        logger.warning("Stream generation failed: %s", e)
                        accumulated = ""

                question = accumulated.strip() or None

                # 3. 持久化新状态
                if is_completed:
                    session.status = "completed"
                    session.ended_at = _now()
                    session.report_data = {
                        "summary": "本场模拟面试已结束。",
                        "strengths": ["能持续回答问题并完成整场面试。"],
                        "weaknesses": _collect_weaknesses(list(session.turns or [])),
                        "next_training_plan": [
                            "每个回答都补足背景、动作、结果。",
                            "突出个人贡献，避免只讲团队。",
                            "尽量加入量化指标和复盘结论。",
                        ],
                    }
                    db.commit()
                    db.refresh(session)
                    done_payload = {
                        "type": "done",
                        "next_action": "completed",
                        "session": _serialize_session(session),
                    }
                else:
                    if force_next_round:
                        next_round = rounds[next_round_index]
                        new_round_type = next_round["type"]
                        new_round_goal = next_round["goal"]
                    else:
                        new_round_type = current_round["type"]
                        new_round_goal = current_round["goal"]
                    if not question:
                        question = "挑一个你最能代表岗位匹配度的项目，讲清楚背景、目标、你的动作和结果。"
                    next_turn = InterviewTurn(
                        session_id=session.id,
                        turn_index=session.current_turn_index + 1,
                        round_index=next_round_index,
                        question=question,
                        question_type=new_round_type,
                        intent=new_round_goal,
                        status="asked",
                        asked_at=_now(),
                    )
                    session.current_turn_index += 1
                    session.current_round_index = next_round_index
                    session.status = "waiting_user_answer"
                    db.add(next_turn)
                    db.commit()
                    db.refresh(session)
                    done_payload = {
                        "type": "done",
                        "next_action": "next_question",
                        "message": question,
                        "session": _serialize_session(session),
                    }

                logger.info("Interview stream completed next_action=%s", done_payload["next_action"])
                observer.finish(done_payload.get("message") or done_payload["next_action"])
                yield f"data: {json.dumps(done_payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{session_id}/end", response_model=InterviewActionResponse)
async def end_interview(
    session_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于让用户主动结束当前面试。"""
    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session or session.user_id != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found")

    turns = list(session.turns or [])
    session.status = "completed"
    session.ended_at = _now()
    if session.report_data is None:
        session.report_data = {
            "summary": "用户主动结束了本场模拟面试。",
            "strengths": ["已完成至少一轮结构化问答。"] if turns else [],
            "weaknesses": _collect_weaknesses(turns),
            "next_training_plan": [
                "继续训练项目深挖回答。",
                "回答时优先讲个人贡献和结果。",
            ],
        }
    db.commit()
    db.refresh(session)
    return InterviewActionResponse(session=_serialize_session(session), next_action="completed")


@router.get("/{session_id}/report", response_model=InterviewActionResponse)
async def get_interview_report(
    session_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于返回指定面试的最终报告视图。"""
    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session or session.user_id != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found")
    return InterviewActionResponse(session=_serialize_session(session))
