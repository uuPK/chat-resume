
from __future__ import annotations

import asyncio
import json
import logging
from datetime import timedelta
from typing import Any, NoReturn, cast

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy.orm import Session

from app.entrypoints.http.deps import (
    authenticate_token_with_db,
    get_current_user,
)
from app.infra.config import settings
from app.prompts import load_prompt
from app.infra.database import get_db
from app.models.interview import InterviewSession, InterviewTurn
from app.models.resume import Resume
from app.services.errors import (
    ServiceError,
    ServiceNotFoundError,
    ServicePermissionError,
)
from app.services.interview.session_service import (
    get_session_for_user,
    record_realtime_interview_message,
)
from app.services.rag.retrieval import retrieve_interview_questions

logger = logging.getLogger(__name__)

router = APIRouter()
_WS_POLICY_VIOLATION = status.WS_1008_POLICY_VIOLATION
_INTERVIEWER_PROMPT = load_prompt("interviewer_agent")
_SYSTEM_ROLE_MAX_CHARS = 4000
_RESUME_CONTEXT_CHARS = 700
_JD_CONTEXT_CHARS = 700
_HISTORY_CONTEXT_CHARS = 900
_PLAN_CONTEXT_CHARS = 600


def _raise_service_http_error(exc: ServiceError) -> NoReturn:
    """用于抛出服务HTTP错误。"""
    if isinstance(exc, ServicePermissionError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    if isinstance(exc, ServiceNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=str(exc),
    ) from exc


@router.post("/{session_id}/realtime-token")
async def get_realtime_session_token(
    session_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """为 WebSocket 连接生成一个临时的、单次使用的授权 Token。"""
    try:
        get_session_for_user(db, session_id, current_user["id"])
    except ServiceError as exc:
        _raise_service_http_error(exc)

    from app.infra.security import create_access_token

    # 签发一个 5 分钟内有效的临时 Token，用于 WebSocket 鉴权
    temp_token = create_access_token(
        subject=str(current_user["id"]),
        expires_delta=timedelta(minutes=5),
    )
    return {"token": temp_token}


def _render_interviewer_prompt(
    *,
    target_title: str,
    target_company: str,
    language: str,
    difficulty: str,
    jd_text: str,
    resume_text: str = "",
    interview_history: str = "",
    interview_plan: str = "",
    rag_questions: str = "",
) -> str:
    """用于从文件模板渲染模拟面试官系统提示词。"""
    return _INTERVIEWER_PROMPT.render(
        prefers_chinese=_prefers_chinese(language),
        target_title=target_title,
        target_company=target_company,
        language=language,
        difficulty=difficulty,
        jd_text=jd_text,
        resume_text=resume_text,
        interview_history=interview_history,
        interview_plan=interview_plan,
        rag_questions=rag_questions,
    )


def _build_greeting(
    *, target_title: str, target_company: str, language: str
) -> str:
    """Build the interviewer's first greeting for a new session."""
    has_context = bool(target_title.strip() and target_company.strip())
    if _prefers_chinese(language):
        if has_context:
            return (
                f"你好，欢迎来到今天的模拟面试。"
                f"我们将围绕 {target_company} 的 {target_title} 岗位进行面试。"
                f"准备好了就告诉我，我们随时可以开始。"
            )
        return "你好，欢迎来到模拟面试。请先做一个简短的自我介绍吧。"
    if has_context:
        return (
            f"Hello and welcome to your mock interview. "
            f"Today we'll be focusing on the {target_title} role at {target_company}. "
            f"Let me know when you're ready to begin."
        )
    return "Hello and welcome. Please start with a brief self-introduction."


def _prefers_chinese(language: str) -> bool:
    """Return whether the interviewer should speak Chinese."""
    normalized = language.strip().lower()
    return normalized.startswith("zh") or "chinese" in normalized or "中文" in language


async def _close_ws_policy_violation(websocket: WebSocket, reason: str) -> None:
    """用于关闭WebSocket策略违规。"""
    await websocket.close(code=_WS_POLICY_VIOLATION, reason=reason)


async def _authorize_realtime_session_ws(
    websocket: WebSocket,
    *,
    session_id: int,
    db: Session,
) -> InterviewSession | None:
    """Authenticate a realtime interview WebSocket connection."""
    token = websocket.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if not token:
        token = websocket.query_params.get("token")

    if not token:
        await _close_ws_policy_violation(websocket, "Missing access token")
        return None

    try:
        _, current_user = authenticate_token_with_db(token, db)
    except HTTPException:
        await _close_ws_policy_violation(websocket, "Invalid access token")
        return None

    user_id = int(current_user["id"])

    try:
        return get_session_for_user(db, session_id, user_id)
    except ServiceError:
        await _close_ws_policy_violation(websocket, "Interview session not found")
        return None


def _extract_resume_text(resume_content: dict) -> str:
    """把结构化简历 JSON 转为面试官可读的纯文本摘要。"""
    lines: list[str] = []

    pi = resume_content.get("personal_info") or {}
    name = pi.get("name") or pi.get("full_name") or ""
    if name:
        lines.append(f"候选人姓名：{name}")

    summary = resume_content.get("summary") or {}
    summary_text = summary.get("content") or summary.get("text") or ""
    if summary_text:
        lines.append(f"个人总结：{summary_text[:500]}")

    for exp in (resume_content.get("work_experience") or [])[:5]:
        company = exp.get("company") or ""
        title = exp.get("title") or exp.get("position") or ""
        duration = f"{exp.get('start_date','')}-{exp.get('end_date','')}"
        desc = exp.get("description") or exp.get("responsibilities") or ""
        if isinstance(desc, list):
            desc = "；".join(str(d) for d in desc)
        lines.append(f"工作经历：{company} | {title} | {duration}\n{str(desc)[:400]}")

    for edu in (resume_content.get("education") or [])[:3]:
        school = edu.get("school") or edu.get("institution") or ""
        major = edu.get("major") or edu.get("field") or ""
        degree = edu.get("degree") or ""
        lines.append(f"教育背景：{school} | {major} | {degree}")

    for proj in (resume_content.get("projects") or [])[:3]:
        proj_name = proj.get("name") or ""
        proj_desc = proj.get("description") or ""
        if isinstance(proj_desc, list):
            proj_desc = "；".join(str(d) for d in proj_desc)
        lines.append(f"项目经历：{proj_name}\n{str(proj_desc)[:300]}")

    skill_items: list[str] = []
    for skill in (resume_content.get("skills") or [])[:5]:
        items = skill.get("items") or []
        skill_items.extend(str(i) for i in items[:8])
    if skill_items:
        lines.append(f"技能：{', '.join(skill_items)}")

    return "\n\n".join(lines)


def _build_interviewer_system_role(
    *,
    target_title: str,
    target_company: str,
    language: str,
    difficulty: str,
    jd_text: str,
    resume_text: str = "",
    interview_history: str = "",
    interview_plan: str = "",
    rag_questions: str = "",
) -> str:
    """Build the system prompt used by the realtime interview agent."""
    return _render_interviewer_prompt(
        target_title=target_title,
        target_company=target_company,
        language=language,
        difficulty=difficulty,
        jd_text=jd_text[:_JD_CONTEXT_CHARS],
        interview_plan=interview_plan[:_PLAN_CONTEXT_CHARS],
        resume_text=resume_text[:_RESUME_CONTEXT_CHARS],
        interview_history=interview_history[:_HISTORY_CONTEXT_CHARS],
        rag_questions=rag_questions,
    ).strip()[:_SYSTEM_ROLE_MAX_CHARS]


def _build_interview_plan_context(plan: Any) -> str:
    """把结构化面试计划压缩成实时模型可读的短上下文。"""
    if not isinstance(plan, dict):
        return ""
    dimensions = (
        plan.get("dimensions") if isinstance(plan.get("dimensions"), list) else []
    )
    stages = plan.get("stages") if isinstance(plan.get("stages"), list) else []
    claims = (
        plan.get("resume_claims") if isinstance(plan.get("resume_claims"), list) else []
    )
    lines: list[str] = []
    if dimensions:
        lines.append("评分维度：" + "、".join(str(item) for item in dimensions[:6]))
    if stages:
        names = [
            str(stage.get("name"))
            for stage in stages[:5]
            if isinstance(stage, dict) and stage.get("name")
        ]
        if names:
            lines.append("阶段：" + " -> ".join(names))
    if claims:
        lines.append("重点核验简历主张：" + "；".join(str(item) for item in claims[:3]))
    jd_focus = str(plan.get("jd_focus") or "")
    if jd_focus:
        lines.append("JD 重点：" + jd_focus[:160])
    return "\n".join(lines)


def _build_interview_history(turns: list[InterviewTurn]) -> str:
    """把已有语音面试轮次整理成给实时模型续聊的短 transcript。"""
    lines: list[str] = []
    for turn in turns[-12:]:
        question = (turn.question or "").strip()
        answer = (turn.answer or "").strip()
        if question:
            lines.append(f"面试官：{question}")
        if answer:
            lines.append(f"候选人：{answer}")
    return "\n".join(lines)


async def run_realtime_interview_session(
    websocket: WebSocket,
    session_id: int,
    system_role: str,
    existing_turns: list[InterviewTurn],
    greeting: str,
    on_text_message: Any,
):
    """使用 LangGraph 架构（Supervisor -> Experts）进行面试会话。"""
    await websocket.accept()
    await websocket.send_json({"type": "ready", "session_id": f"sandbox_{session_id}"})

    if not greeting and not existing_turns:
        greeting = "你好，我是您的 AI 面试官。请先做一个简短的自我介绍吧。"

    if greeting and not existing_turns:
        await websocket.send_json({
            "type": "greeting",
            "role": "interviewer",
            "text": greeting,
        })
        on_text_message("interviewer", greeting)

    from app.agents.interview.graph import interview_agent
    from app.agents.interview.state import InterviewState
    from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
    from langchain_core.runnables import RunnableConfig

    initial_messages: list[BaseMessage] = [SystemMessage(content=system_role)]
    for turn in existing_turns:
        if turn.question:
            initial_messages.append(AIMessage(content=turn.question))
        if turn.answer:
            initial_messages.append(HumanMessage(content=turn.answer))

    config: RunnableConfig = {"configurable": {"thread_id": str(session_id)}}

    try:
        while True:
            msg = await websocket.receive()
            if msg["type"] == "websocket.disconnect":
                break
            if msg["type"] == "websocket.receive":
                user_text = ""
                trigger_reply = False
                
                if "text" in msg and msg["text"]:
                    try:
                        data = json.loads(msg["text"])
                        if data.get("type") == "text":
                            trigger_reply = True
                            user_text = data.get("text", "")
                            on_text_message("candidate", user_text)
                    except json.JSONDecodeError:
                        pass
                elif "bytes" in msg and msg["bytes"]:
                    pass
                
                if trigger_reply and user_text:
                    await websocket.send_json({
                        "type": "event",
                        "event": 459, # User Speech recognized event
                        "text": user_text,
                    })
                    
                    full_reply = ""
                    input_state = cast(
                        InterviewState,
                        {"messages": [HumanMessage(content=user_text)]},
                    )
                    
                    # 第一次请求如果检查点里没有状态，手动把预置信息（系统词+历史）带上
                    current_state = interview_agent.get_state(config)
                    if not current_state.values.get("messages"):
                        input_state = cast(
                            InterviewState,
                            {
                                "messages": initial_messages
                                + [HumanMessage(content=user_text)]
                            },
                        )
                    
                    try:
                        async for raw_item in interview_agent.astream(
                            input_state,
                            config=config,
                            stream_mode="messages",
                        ):
                            msg_obj, metadata = cast(tuple[Any, dict[str, Any]], raw_item)
                            node = metadata.get("langgraph_node")
                            if node in ("Tech_Expert", "HR_Expert") and msg_obj.content and not msg_obj.tool_calls:
                                full_reply += msg_obj.content
                                await websocket.send_json({
                                    "type": "event",
                                    "event": 550, # Interviewer Speech event
                                    "text": full_reply,
                                    "is_final": False,
                                })
                                
                        await websocket.send_json({
                            "type": "event",
                            "event": 550,
                            "text": full_reply,
                            "is_final": True,
                        })
                        on_text_message("interviewer", full_reply)
                        
                    except Exception as e:
                        logger.error(f"Chat service error: {e}")
                        await websocket.send_json({
                            "type": "error",
                            "message": "抱歉，由于网络问题无法获取回复。"
                        })
    except WebSocketDisconnect:
        pass


@router.websocket("/{session_id}/realtime")
async def realtime_interview_ws(
    websocket: WebSocket,
    session_id: int,
    db: Session = Depends(get_db),
):
    """Run the authenticated realtime interview WebSocket."""
    interview_session = await _authorize_realtime_session_ws(
        websocket,
        session_id=session_id,
        db=db,
    )
    if interview_session is None:
        return

    # 加载面试上下文构建 system_role 和开场白
    system_role = ""
    greeting = ""
    if interview_session:
        existing_turns = (
            db.query(InterviewTurn)
            .filter(InterviewTurn.session_id == session_id)
            .order_by(InterviewTurn.turn_index)
            .all()
        )
        # 加载对应简历内容
        resume_text = ""
        if interview_session.resume_id:
            resume = (
                db.query(Resume)
                .filter(Resume.id == interview_session.resume_id)
                .first()
            )
            if resume and resume.content:
                resume_text = _extract_resume_text(
                    resume.content if isinstance(resume.content, dict) else {}
                )

        plan_context = _build_interview_plan_context(interview_session.plan_json)
        
        rag_query = f"{interview_session.target_title or ''} {resume_text[:200]}"
        try:
            rag_questions = await retrieve_interview_questions(rag_query)
        except Exception:
            logger.exception(
                "interview.rag_retrieval_failed interview_session_id=%s",
                session_id,
            )
            rag_questions = ""

        system_role = _build_interviewer_system_role(
            target_title=interview_session.target_title or "目标岗位",
            target_company=interview_session.target_company or "目标公司",
            language=interview_session.language,
            difficulty=interview_session.difficulty,
            jd_text=interview_session.jd_text or "",
            resume_text=resume_text,
            interview_history=_build_interview_history(existing_turns),
            interview_plan=plan_context,
            rag_questions=rag_questions,
        )
        if not existing_turns:
            greeting = _build_greeting(
                target_title=interview_session.target_title or "",
                target_company=interview_session.target_company or "",
                language=interview_session.language,
            )

    def persist_message(role: str, text: str) -> None:
        """Persist one finalized realtime interview message."""
        record_realtime_interview_message(
            db=db,
            session_id=session_id,
            role=role,
            text=text,
        )
        logger.info(
            "interview.ws.message_persisted interview_session_id=%s role=%s chars=%d",
            session_id,
            role,
            len(text),
        )

    await run_realtime_interview_session(
        websocket=websocket,
        session_id=session_id,
        system_role=system_role,
        existing_turns=existing_turns,
        greeting=greeting,
        on_text_message=persist_message,
    )

