"""
结构化面试 API

提供面试 session / turn 的最小闭环接口。
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.agents.definitions import InterviewerAgent
from app.infra.database import get_db
from app.models import InterviewSession, InterviewTurn
from app.schemas.resume import dump_resume_content_for_frontend
from app.services.domain import ResumeService

router = APIRouter()

_interviewer_agent = InterviewerAgent()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_resume_for_user(db: Session, resume_id: int, user_id: int):
    resume = ResumeService(db).get_by_id(resume_id)
    if not resume:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    if resume.owner_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    return resume


def _rounds_for_type(interview_type: str) -> list[dict[str, Any]]:
    if interview_type == "behavioral":
        return [
            {"type": "warmup", "goal": "自我介绍与背景确认"},
            {"type": "behavioral", "goal": "行为事件与协作能力"},
            {"type": "behavioral", "goal": "冲突处理与复盘能力"},
            {"type": "closing", "goal": "总结与反问"},
        ]
    if interview_type == "technical":
        return [
            {"type": "warmup", "goal": "自我介绍与岗位匹配"},
            {"type": "resume_deep_dive", "goal": "项目真实性与个人贡献"},
            {"type": "technical", "goal": "技术深度与工程判断"},
            {"type": "technical", "goal": "系统设计与排障能力"},
            {"type": "closing", "goal": "总结与反问"},
        ]
    return [
        {"type": "warmup", "goal": "自我介绍与背景确认"},
        {"type": "resume_deep_dive", "goal": "项目深挖与个人贡献"},
        {"type": "behavioral", "goal": "行为能力与沟通协作"},
        {"type": "closing", "goal": "总结与反问"},
    ]


def _build_plan(resume_content: dict[str, Any], interview_type: str) -> dict[str, Any]:
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
    return {
        "id": turn.id,
        "turn_index": turn.turn_index,
        "round_index": turn.round_index,
        "question": turn.question,
        "question_type": turn.question_type,
        "intent": turn.intent,
        "expected_points": turn.expected_points,
        "answer": turn.answer,
        "evaluation": turn.evaluation,
        "score": turn.score,
        "follow_up_count": turn.follow_up_count,
        "status": turn.status,
        "asked_at": turn.asked_at,
        "answered_at": turn.answered_at,
    }


def _serialize_session(session: InterviewSession) -> dict[str, Any]:
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
        "overall_score": session.overall_score,
        "report_data": session.report_data,
        "started_at": session.started_at,
        "ended_at": session.ended_at,
        "turns": [_serialize_turn(turn) for turn in turns],
        "current_turn": _serialize_turn(turns[-1]) if turns else None,
    }


def _latest_turn(session: InterviewSession) -> Optional[InterviewTurn]:
    turns = list(session.turns or [])
    return turns[-1] if turns else None




async def _generate_question(
    *,
    resume_content: dict[str, Any],
    history: list[dict[str, str]],
    prompt: str,
) -> str:
    result = await _interviewer_agent.chat(
        user_message=prompt,
        resume_content=resume_content,
        conversation_history=history,
    )
    return (result.get("content") or "").strip()


def _fallback_evaluation(question: str, answer: str) -> dict[str, Any]:
    """规则兜底：LLM 评估失败时使用。"""
    normalized = (answer or "").strip()
    score = 8
    gaps: list[str] = []
    if len(normalized) < 60:
        score = 5
        gaps.append("回答偏短，缺少背景和结果")
    if "我" not in normalized:
        score = min(score, 6)
        gaps.append("个人贡献不够明确")
    if not any(ch.isdigit() for ch in normalized):
        score = min(score, 6)
        gaps.append("缺少量化结果或具体指标")
    should_follow_up = len(normalized) < 60 or len(gaps) >= 2
    return {
        "summary": f'围绕"{question[:30]}"的回答已完成初步评估。',
        "dimension_scores": {
            "clarity": max(1, min(10, score)),
            "depth": max(1, min(10, score - 1 if should_follow_up else score)),
            "relevance": max(1, min(10, score)),
        },
        "evidence": [],
        "gaps": gaps,
        "should_follow_up": should_follow_up,
        "score": score,
    }


async def _evaluate_answer_with_llm(
    *,
    question: str,
    answer: str,
    resume_content: dict[str, Any],
    history: list[dict[str, str]],
) -> dict[str, Any]:
    """用 LLM 评估候选人回答，解析失败时 fallback 到规则。"""
    prompt = (
        f"[EVALUATE]\n"
        f"面试问题：{question}\n"
        f"候选人回答：{answer}"
    )
    try:
        result = await _interviewer_agent.chat(
            user_message=prompt,
            resume_content=resume_content,
            conversation_history=history,
        )
        raw = (result.get("content") or "").strip()
        # 兼容模型偶尔包裹 markdown 代码块的情况
        json_str = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL).strip()
        data = json.loads(json_str)
        score_raw = data.get("score", 7)
        score = max(1, min(10, int(round(float(score_raw)))))
        dim = data.get("dimension_scores", {})
        return {
            "summary": str(data.get("summary", "")),
            "dimension_scores": {
                "clarity": max(1, min(10, int(dim.get("clarity", score)))),
                "depth": max(1, min(10, int(dim.get("depth", score)))),
                "relevance": max(1, min(10, int(dim.get("relevance", score)))),
            },
            "evidence": list(data.get("evidence", []))[:2],
            "gaps": list(data.get("gaps", []))[:3],
            "should_follow_up": bool(data.get("should_follow_up", False)),
            "score": score,
        }
    except Exception:
        logger.warning("LLM evaluation failed, falling back to rule-based evaluation")
        return _fallback_evaluation(question, answer)


class InterviewCreateRequest(BaseModel):
    resume_id: int
    target_title: str = ""
    target_company: str = ""
    jd_text: str = ""
    interview_type: str = "general"
    difficulty: str = "medium"
    language: str = "zh-CN"
    mode: str = "text"


class InterviewAnswerRequest(BaseModel):
    answer: str = Field(min_length=1)


class InterviewActionResponse(BaseModel):
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


@router.get("/", response_model=List[Dict[str, Any]])
async def list_interviews(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sessions = (
        db.query(InterviewSession)
        .filter(InterviewSession.user_id == current_user["id"])
        .order_by(InterviewSession.id.desc())
        .all()
    )
    return [_serialize_session(session) for session in sessions]


@router.get("/{session_id}", response_model=InterviewActionResponse)
async def get_interview(
    session_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session or session.user_id != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found")
    return InterviewActionResponse(session=_serialize_session(session))


@router.post("/{session_id}/start", response_model=InterviewActionResponse)
async def start_interview(
    session_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session or session.user_id != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found")
    if session.status not in {"created", "interview_ready"}:
        return InterviewActionResponse(session=_serialize_session(session))

    resume = _get_resume_for_user(db, session.resume_id, current_user["id"])
    resume_content = resume.content if isinstance(resume.content, dict) else {}
    rounds = ((session.plan_json or {}).get("rounds") or [])
    round_goal = rounds[0]["goal"] if rounds else "自我介绍与岗位匹配"
    question = await _generate_question(
        resume_content=resume_content,
        history=[],
        prompt=f"开始一场模拟面试。当前轮目标：{round_goal}。请直接提出第一题。",
    )
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
    return InterviewActionResponse(
        session=_serialize_session(session),
        message=question,
        next_action="answer",
    )


@router.post("/{session_id}/answer", response_model=InterviewActionResponse)
async def answer_interview(
    session_id: int,
    request: InterviewAnswerRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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
    history: list[dict[str, str]] = []
    for item in list(session.turns or []):
        history.append({"role": "assistant", "content": item.question})
        if item.answer and item is not turn:
            history.append({"role": "user", "content": item.answer})

    evaluation = await _evaluate_answer_with_llm(
        question=turn.question,
        answer=answer_text,
        resume_content=resume_content,
        history=history,
    )
    should_follow_up = evaluation["should_follow_up"] and turn.follow_up_count < 2

    turn.answer = answer_text
    turn.answered_at = _now()
    turn.evaluation = evaluation
    turn.score = evaluation["score"]
    turn.status = "evaluated"

    if should_follow_up:
        prompt = (
            f"用户刚回答了这个问题：{turn.question}\n"
            f"回答内容：{answer_text}\n"
            f"当前缺口：{'；'.join(evaluation['gaps']) or '继续深挖细节'}\n"
            "请像真实面试官一样只追问一个最关键的问题。"
        )
        question = await _generate_question(resume_content=resume_content, history=history, prompt=prompt)
        if not question:
            question = "你刚才讲得还不够具体。请补充你的个人贡献、关键动作和最终结果。"
        next_turn = InterviewTurn(
            session_id=session.id,
            turn_index=session.current_turn_index + 1,
            round_index=turn.round_index,
            question=question,
            question_type=turn.question_type,
            intent=turn.intent,
            expected_points=turn.expected_points,
            follow_up_count=turn.follow_up_count + 1,
            status="asked",
            asked_at=_now(),
        )
        turn.status = "done"
        session.current_turn_index += 1
        session.status = "waiting_user_answer"
        db.add(next_turn)
        db.commit()
        db.refresh(session)
        return InterviewActionResponse(
            session=_serialize_session(session),
            evaluation=evaluation,
            message=question,
            next_action="follow_up",
        )

    rounds = ((session.plan_json or {}).get("rounds") or [])
    next_round_index = turn.round_index + 1
    if next_round_index >= len(rounds):
        turn.status = "done"
        turns = list(session.turns or [])
        scores = [item.score for item in turns if item.score is not None]
        session.overall_score = int(round(sum(scores) / len(scores))) if scores else None
        session.status = "completed"
        session.ended_at = _now()
        session.report_data = {
            "summary": "本场模拟面试已结束。",
            "strengths": ["能持续回答问题并完成整场面试。"],
            "weaknesses": list(dict.fromkeys(g for item in turns for g in ((item.evaluation or {}).get("gaps") or [])))[:5],
            "next_training_plan": [
                "每个回答都补足背景、动作、结果。",
                "突出个人贡献，避免只讲团队。",
                "尽量加入量化指标和复盘结论。",
            ],
        }
        db.commit()
        db.refresh(session)
        return InterviewActionResponse(
            session=_serialize_session(session),
            evaluation=evaluation,
            next_action="completed",
        )

    next_round = rounds[next_round_index]
    prompt = f"进入下一轮模拟面试。当前轮目标：{next_round['goal']}。请直接提出下一题。"
    question = await _generate_question(resume_content=resume_content, history=history, prompt=prompt)
    if not question:
        question = "挑一个你最能代表岗位匹配度的项目，讲清楚背景、目标、你的动作和结果。"
    next_turn = InterviewTurn(
        session_id=session.id,
        turn_index=session.current_turn_index + 1,
        round_index=next_round_index,
        question=question,
        question_type=next_round["type"],
        intent=next_round["goal"],
        status="asked",
        asked_at=_now(),
    )
    turn.status = "done"
    session.current_turn_index += 1
    session.current_round_index = next_round_index
    session.status = "waiting_user_answer"
    db.add(next_turn)
    db.commit()
    db.refresh(session)
    return InterviewActionResponse(
        session=_serialize_session(session),
        evaluation=evaluation,
        message=question,
        next_action="next_question",
    )


@router.post("/{session_id}/answer/stream")
async def answer_interview_stream(
    session_id: int,
    request: InterviewAnswerRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """流式版本：先评估，再流式生成面试官回复，最后发 done 事件。"""
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

    history: list[dict[str, str]] = []
    for item in list(session.turns or []):
        history.append({"role": "assistant", "content": item.question})
        if item.answer and item is not turn:
            history.append({"role": "user", "content": item.answer})

    # 1. 非流式评估（必须先完成才能决定后续行为）
    evaluation = await _evaluate_answer_with_llm(
        question=turn.question,
        answer=answer_text,
        resume_content=resume_content,
        history=history,
    )
    should_follow_up = evaluation["should_follow_up"] and turn.follow_up_count < 2

    turn.answer = answer_text
    turn.answered_at = _now()
    turn.evaluation = evaluation
    turn.score = evaluation["score"]
    turn.status = "evaluated"

    async def generate():
        nonlocal session

        # 2. 决定 prompt
        if should_follow_up:
            prompt = (
                f"用户刚回答了这个问题：{turn.question}\n"
                f"回答内容：{answer_text}\n"
                f"当前缺口：{'；'.join(evaluation['gaps']) or '继续深挖细节'}\n"
                "请像真实面试官一样只追问一个最关键的问题。"
            )
        else:
            rounds = ((session.plan_json or {}).get("rounds") or [])
            next_round_index = turn.round_index + 1
            is_last_round = next_round_index >= len(rounds)
            if is_last_round:
                prompt = None  # 面试结束，无需生成问题
            else:
                next_round = rounds[next_round_index]
                prompt = f"进入下一轮模拟面试。当前轮目标：{next_round['goal']}。请直接提出下一题。"

        # 3. 流式生成问题（结束场景跳过）
        accumulated = ""
        if prompt is not None:
            try:
                async for chunk in _interviewer_agent.chat_stream(
                    user_message=prompt,
                    resume_content=resume_content,
                    conversation_history=history,
                ):
                    token = chunk.get("content") or ""
                    if token:
                        accumulated += token
                        yield f"data: {json.dumps({'type': 'token', 'content': token}, ensure_ascii=False)}\n\n"
            except Exception as e:
                logger.warning("Stream generation failed: %s", e)
                accumulated = ""

        question = accumulated.strip() or None

        # 4. 持久化新状态
        if should_follow_up:
            if not question:
                question = "你刚才讲得还不够具体。请补充你的个人贡献、关键动作和最终结果。"
            next_turn = InterviewTurn(
                session_id=session.id,
                turn_index=session.current_turn_index + 1,
                round_index=turn.round_index,
                question=question,
                question_type=turn.question_type,
                intent=turn.intent,
                expected_points=turn.expected_points,
                follow_up_count=turn.follow_up_count + 1,
                status="asked",
                asked_at=_now(),
            )
            turn.status = "done"
            session.current_turn_index += 1
            session.status = "waiting_user_answer"
            db.add(next_turn)
            db.commit()
            db.refresh(session)
            done_payload = {
                "type": "done",
                "next_action": "follow_up",
                "evaluation": evaluation,
                "message": question,
                "session": _serialize_session(session),
            }
        else:
            rounds = ((session.plan_json or {}).get("rounds") or [])
            next_round_index = turn.round_index + 1
            if next_round_index >= len(rounds):
                turn.status = "done"
                turns = list(session.turns or [])
                scores = [item.score for item in turns if item.score is not None]
                session.overall_score = int(round(sum(scores) / len(scores))) if scores else None
                session.status = "completed"
                session.ended_at = _now()
                session.report_data = {
                    "summary": "本场模拟面试已结束。",
                    "strengths": ["能持续回答问题并完成整场面试。"],
                    "weaknesses": list(dict.fromkeys(
                        g for item in turns for g in ((item.evaluation or {}).get("gaps") or [])
                    ))[:5],
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
                    "evaluation": evaluation,
                    "session": _serialize_session(session),
                }
            else:
                next_round = rounds[next_round_index]
                if not question:
                    question = "挑一个你最能代表岗位匹配度的项目，讲清楚背景、目标、你的动作和结果。"
                next_turn = InterviewTurn(
                    session_id=session.id,
                    turn_index=session.current_turn_index + 1,
                    round_index=next_round_index,
                    question=question,
                    question_type=next_round["type"],
                    intent=next_round["goal"],
                    status="asked",
                    asked_at=_now(),
                )
                turn.status = "done"
                session.current_turn_index += 1
                session.current_round_index = next_round_index
                session.status = "waiting_user_answer"
                db.add(next_turn)
                db.commit()
                db.refresh(session)
                done_payload = {
                    "type": "done",
                    "next_action": "next_question",
                    "evaluation": evaluation,
                    "message": question,
                    "session": _serialize_session(session),
                }

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
    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session or session.user_id != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found")

    turns = list(session.turns or [])
    scores = [turn.score for turn in turns if turn.score is not None]
    session.overall_score = int(round(sum(scores) / len(scores))) if scores else None
    session.status = "completed"
    session.ended_at = _now()
    if session.report_data is None:
        session.report_data = {
            "summary": "用户主动结束了本场模拟面试。",
            "strengths": ["已完成至少一轮结构化问答。"] if turns else [],
            "weaknesses": list(dict.fromkeys(g for turn in turns for g in ((turn.evaluation or {}).get("gaps") or [])))[:5],
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
    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session or session.user_id != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found")
    return InterviewActionResponse(session=_serialize_session(session))
