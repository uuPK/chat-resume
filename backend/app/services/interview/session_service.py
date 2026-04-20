"""
面试会话服务模块

用于承接结构化面试的会话创建、推进、流式答题和结束编排。
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import case, func
from sqlalchemy.orm import Session, noload

from app.agents.interview import InterviewerAgent
from app.infra.langfuse_observer import LangfuseRunObserver
from app.infra.request_context import log_context
from app.models import InterviewSession, InterviewTurn
from app.services.domain import ResumeService
from app.services.interview.evaluation_service import (
    build_interview_report,
    build_session_factory,
    build_turn_history,
    fallback_hint,
    generate_question,
    log_async_task_failure,
    persist_turn_evaluation,
)
from app.services.interview.planning_service import (
    build_first_round_prompt,
    build_hint_prompt,
    build_next_round_prompt,
    build_plan,
    build_same_round_prompt,
)
from app.services.interview.serializer import (
    latest_turn,
    serialize_session,
    serialize_session_summary,
)

_interviewer_agent = InterviewerAgent()


def now() -> datetime:
    """用于统一生成带时区的当前时间。"""
    return datetime.now(timezone.utc)


def get_resume_for_user(db: Session, resume_id: int, user_id: int):
    """用于校验用户对目标简历的访问权限。"""
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
    """用于统一读取并校验当前用户拥有的面试 session。"""
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
    """用于创建一场新的结构化模拟面试。"""
    resume = get_resume_for_user(db, resume_id, user_id)
    resume_content = resume.content if isinstance(resume.content, dict) else {}
    plan = build_plan(resume_content, interview_type)
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
        plan_json=plan,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


async def get_interview_hints(
    *,
    db: Session,
    user_id: int,
    session_id: int,
    http_request: Request,
) -> list[str]:
    """用于在练习模式下为当前题目生成简短提示。"""
    session = get_session_or_404(db, session_id, user_id)
    if session.mode != "practice":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Hints are only available in practice mode",
        )

    turn = latest_turn(session)
    if not turn or turn.status != "asked":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="No active question to hint"
        )

    resume = get_resume_for_user(db, session.resume_id, user_id)
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
        user_id=user_id,
        input_text=turn.question,
        metadata={
            "interview_session_id": session.id,
            "resume_id": session.resume_id,
            "request_id": getattr(http_request.state, "request_id", None),
        },
    )
    prompt = build_hint_prompt(
        question_type=turn.question_type,
        question=turn.question,
        round_goal=turn.intent or "",
        target_title=session.target_title or "",
    )
    hints = fallback_hint(turn)
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
    return hints


def list_interview_sessions(*, db: Session, user_id: int) -> list[dict[str, Any]]:
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
    """用于删除当前用户的一场面试记录及其关联轮次。"""
    session = get_session_or_404(db, session_id, user_id)
    db.delete(session)
    db.commit()


async def start_interview_session(
    *,
    db: Session,
    user_id: int,
    session_id: int,
    http_request: Request,
) -> tuple[InterviewSession, str | None, str | None]:
    """用于启动一场待开始的面试并生成第一题。"""
    session = get_session_or_404(db, session_id, user_id)
    if session.status not in {"created", "interview_ready"}:
        return session, None, None

    resume = get_resume_for_user(db, session.resume_id, user_id)
    resume_content = resume.content if isinstance(resume.content, dict) else {}
    run_id = uuid4().hex
    observer = LangfuseRunObserver(
        run_id=run_id,
        agent_type="interview",
        run_kind="start_interview",
        user_id=user_id,
        input_text="开始模拟面试并生成第一题",
        metadata={
            "interview_session_id": session.id,
            "resume_id": session.resume_id,
            "request_id": getattr(http_request.state, "request_id", None),
        },
    )
    rounds = (session.plan_json or {}).get("rounds") or []
    first_round = rounds[0] if rounds else {}
    round_goal = first_round.get("goal", "自我介绍与岗位匹配")
    try:
        with observer:
            question = await generate_question(
                resume_content=resume_content,
                history=[],
                prompt=build_first_round_prompt(
                    first_round.get("type", "warmup"), round_goal
                ),
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
        asked_at=now(),
    )
    session.status = "waiting_user_answer"
    session.current_turn_index = 1
    session.started_at = session.started_at or now()
    db.add(turn)
    db.commit()
    db.refresh(session)
    observer.finish(question)
    return session, question, "answer"


async def answer_interview_session(
    *,
    db: Session,
    user_id: int,
    session_id: int,
    answer_text: str,
    http_request: Request,
) -> tuple[InterviewSession, str | None, str]:
    """用于处理一次回答并生成下一题或结束面试。"""
    session = get_session_or_404(db, session_id, user_id)
    if session.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Interview already completed"
        )

    turn = latest_turn(session)
    if not turn or turn.status != "asked":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="No active question to answer"
        )

    resume = get_resume_for_user(db, session.resume_id, user_id)
    resume_content = resume.content if isinstance(resume.content, dict) else {}
    run_id = uuid4().hex
    observer = LangfuseRunObserver(
        run_id=run_id,
        agent_type="interview",
        run_kind="answer_interview",
        user_id=user_id,
        input_text=answer_text,
        metadata={
            "interview_session_id": session.id,
            "resume_id": session.resume_id,
            "request_id": getattr(http_request.state, "request_id", None),
        },
    )
    history = build_turn_history(session, current_turn=turn, pending_answer=answer_text)
    background_session_factory = build_session_factory(db)

    turn.answer = answer_text
    turn.answered_at = now()
    turn.status = "done"

    rounds = (session.plan_json or {}).get("rounds") or []
    current_round = rounds[turn.round_index] if turn.round_index < len(rounds) else {}
    max_q = int(current_round.get("max_questions") or 2)
    questions_in_round = sum(
        1 for item in session.turns if item.round_index == turn.round_index
    )
    force_next_round = questions_in_round >= max_q
    next_round_index = turn.round_index + 1 if force_next_round else turn.round_index

    if force_next_round and next_round_index >= len(rounds):
        session.status = "completed"
        session.ended_at = now()
        session.report_data = build_interview_report(
            turns=list(session.turns or []),
            target_title=session.target_title or "",
            target_company=session.target_company or "",
        )
        db.commit()
        db.refresh(session)
        evaluation_task = asyncio.create_task(
            persist_turn_evaluation(
                session_factory=background_session_factory,
                user_id=user_id,
                session_id=session.id,
                turn_id=turn.id,
                question=turn.question,
                answer=answer_text,
                resume_content=resume_content,
                history=history,
                event_callback=None,
            )
        )
        evaluation_task.add_done_callback(log_async_task_failure)
        observer.finish("interview_completed")
        return session, None, "completed"

    if force_next_round:
        next_round = rounds[next_round_index]
        prompt = build_next_round_prompt(next_round["type"], next_round["goal"])
        new_round_index = next_round_index
        new_round_type = next_round["type"]
        new_round_goal = next_round["goal"]
    else:
        remaining = max_q - questions_in_round
        prompt = build_same_round_prompt(
            current_round["type"], current_round["goal"], remaining
        )
        new_round_index = turn.round_index
        new_round_type = current_round["type"]
        new_round_goal = current_round["goal"]

    evaluation_task = asyncio.create_task(
        persist_turn_evaluation(
            session_factory=background_session_factory,
            user_id=user_id,
            session_id=session.id,
            turn_id=turn.id,
            question=turn.question,
            answer=answer_text,
            resume_content=resume_content,
            history=history,
            event_callback=None,
        )
    )
    evaluation_task.add_done_callback(log_async_task_failure)

    try:
        with observer:
            question = await generate_question(
                resume_content=resume_content,
                history=history,
                prompt=prompt,
                event_callback=observer.on_runtime_event,
            )
    except Exception as exc:
        observer.fail(str(exc))
        raise
    if not question:
        question = (
            "挑一个你最能代表岗位匹配度的项目，讲清楚背景、目标、你的动作和结果。"
        )

    next_turn = InterviewTurn(
        session_id=session.id,
        turn_index=session.current_turn_index + 1,
        round_index=new_round_index,
        question=question,
        question_type=new_round_type,
        intent=new_round_goal,
        status="asked",
        asked_at=now(),
    )
    session.current_turn_index += 1
    session.current_round_index = new_round_index
    session.status = "waiting_user_answer"
    db.add(next_turn)
    db.commit()
    db.refresh(session)
    observer.finish(question)
    return session, question, "next_question"


async def stream_answer_interview_session(
    *,
    db: Session,
    user_id: int,
    session_id: int,
    answer_text: str,
    http_request: Request,
) -> StreamingResponse:
    """用于流式生成下一题并在结束时返回最新 session。"""
    session = get_session_or_404(db, session_id, user_id)
    if session.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Interview already completed"
        )

    turn = latest_turn(session)
    if not turn or turn.status != "asked":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="No active question to answer"
        )

    resume = get_resume_for_user(db, session.resume_id, user_id)
    resume_content = resume.content if isinstance(resume.content, dict) else {}
    run_id = uuid4().hex
    observer = LangfuseRunObserver(
        run_id=run_id,
        agent_type="interview",
        run_kind="answer_interview_stream",
        user_id=user_id,
        input_text=answer_text,
        metadata={
            "interview_session_id": session.id,
            "resume_id": session.resume_id,
            "request_id": getattr(http_request.state, "request_id", None),
        },
    )
    history = build_turn_history(session, current_turn=turn, pending_answer=answer_text)
    background_session_factory = build_session_factory(db)

    turn.answer = answer_text
    turn.answered_at = now()
    turn.status = "done"
    db.commit()
    db.refresh(session)

    async def generate():
        nonlocal session
        with log_context(
            request_id=getattr(http_request.state, "request_id", None),
            session_id=str(session_id),
        ):
            with observer:
                rounds = (session.plan_json or {}).get("rounds") or []
                current_round = (
                    rounds[turn.round_index] if turn.round_index < len(rounds) else {}
                )
                max_q = int(current_round.get("max_questions") or 2)
                questions_in_round = sum(
                    1 for item in session.turns if item.round_index == turn.round_index
                )
                force_next_round = questions_in_round >= max_q
                next_round_index = (
                    turn.round_index + 1 if force_next_round else turn.round_index
                )
                is_completed = force_next_round and next_round_index >= len(rounds)

                if is_completed:
                    prompt = None
                elif force_next_round:
                    next_round = rounds[next_round_index]
                    prompt = build_next_round_prompt(
                        next_round["type"], next_round["goal"]
                    )
                else:
                    remaining = max_q - questions_in_round
                    prompt = build_same_round_prompt(
                        current_round["type"], current_round["goal"], remaining
                    )

                queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
                accumulated = ""

                async def stream_next_question() -> None:
                    """用于把下一题的 token 按流式事件推入队列。"""
                    nonlocal accumulated
                    if prompt is None:
                        await queue.put({"type": "question_complete"})
                        return
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
                                await queue.put({"type": "token", "content": token})
                    except Exception as exc:
                        observer.fail(str(exc))
                    finally:
                        await queue.put({"type": "question_complete"})

                async def stream_turn_evaluation() -> None:
                    """用于并行生成当前题评估，并把结果作为事件推入队列。"""
                    if session.mode != "practice":
                        await queue.put({"type": "evaluation_complete"})
                        return
                    try:
                        evaluation_text = await persist_turn_evaluation(
                            session_factory=background_session_factory,
                            user_id=user_id,
                            session_id=session.id,
                            turn_id=turn.id,
                            question=turn.question,
                            answer=answer_text,
                            resume_content=resume_content,
                            history=history,
                            event_callback=None,
                        )
                        await queue.put(
                            {
                                "type": "evaluation",
                                "turn_id": turn.id,
                                "evaluation": evaluation_text,
                            }
                        )
                    finally:
                        await queue.put({"type": "evaluation_complete"})

                question_task = asyncio.create_task(stream_next_question())
                question_task.add_done_callback(log_async_task_failure)
                evaluation_task = asyncio.create_task(stream_turn_evaluation())
                evaluation_task.add_done_callback(log_async_task_failure)

                question_completed = False
                evaluation_completed = session.mode != "practice"
                done_emitted = False

                while not (done_emitted and evaluation_completed):
                    event = await queue.get()
                    event_type = str(event.get("type") or "")

                    if event_type in {"token", "evaluation"}:
                        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                        continue
                    if event_type == "evaluation_complete":
                        evaluation_completed = True
                        continue
                    if event_type != "question_complete":
                        continue

                    question_completed = True
                    question = accumulated.strip() or None

                    if is_completed:
                        session.status = "completed"
                        session.ended_at = now()
                        session.report_data = build_interview_report(
                            turns=list(session.turns or []),
                            target_title=session.target_title or "",
                            target_company=session.target_company or "",
                        )
                        db.commit()
                        db.refresh(session)
                        done_payload = {
                            "type": "done",
                            "next_action": "completed",
                            "session": serialize_session(session),
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
                            question = (
                                "挑一个你最能代表岗位匹配度的项目，"
                                "讲清楚背景、目标、你的动作和结果。"
                            )
                        next_turn = InterviewTurn(
                            session_id=session.id,
                            turn_index=session.current_turn_index + 1,
                            round_index=next_round_index,
                            question=question,
                            question_type=new_round_type,
                            intent=new_round_goal,
                            status="asked",
                            asked_at=now(),
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
                            "session": serialize_session(session),
                        }

                    observer.finish(
                        done_payload.get("message") or done_payload["next_action"]
                    )
                    yield f"data: {json.dumps(done_payload, ensure_ascii=False)}\n\n"
                    done_emitted = True

                if not question_completed:
                    await question_task
                if not evaluation_completed:
                    await evaluation_task

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def end_interview_session(
    *, db: Session, user_id: int, session_id: int
) -> InterviewSession:
    """用于让用户主动结束当前面试。"""
    session = get_session_or_404(db, session_id, user_id)
    turns = list(session.turns or [])
    session.status = "completed"
    session.ended_at = now()
    session.report_data = build_interview_report(
        turns=turns,
        target_title=session.target_title or "",
        target_company=session.target_company or "",
        ended_by_user=True,
    )
    db.commit()
    db.refresh(session)
    return session
