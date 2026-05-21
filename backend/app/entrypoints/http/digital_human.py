"""数字人 API 入口。

负责为豆包端到端语音面试准备会话上下文。
"""

from __future__ import annotations

import logging
from typing import Any, NoReturn
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from pydantic import BaseModel
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
from app.services.digital_human import VolcengineVoiceService
from app.services.errors import (
    ServiceError,
    ServiceNotFoundError,
    ServicePermissionError,
)
from app.services.interview.session_service import (
    get_session_for_user,
    record_voice_interview_message,
)

logger = logging.getLogger(__name__)

router = APIRouter()
_WS_POLICY_VIOLATION = status.WS_1008_POLICY_VIOLATION
_INTERVIEWER_PROMPT = load_prompt("interviewer_agent")
_VOLCENGINE_SYSTEM_ROLE_MAX_CHARS = 4000
_VOLCENGINE_RESUME_CONTEXT_CHARS = 700
_VOLCENGINE_JD_CONTEXT_CHARS = 700
_VOLCENGINE_HISTORY_CONTEXT_CHARS = 900
_VOLCENGINE_PLAN_CONTEXT_CHARS = 600


class DigitalHumanCreateRequest(BaseModel):
    """用于承载创建数字人会话的请求参数。"""

    interview_session_id: int


class DigitalHumanConversationResponse(BaseModel):
    """用于返回前端可安全使用的豆包语音会话信息。"""

    provider: str
    session_id: str = ""
    status: str


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


@router.post("/conversations", response_model=DigitalHumanConversationResponse)
async def create_digital_human_conversation(
    request: DigitalHumanCreateRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于为一场豆包端到端语音面试准备会话。"""
    try:
        get_session_for_user(db, request.interview_session_id, current_user["id"])
    except ServiceError as exc:
        _raise_service_http_error(exc)

    return DigitalHumanConversationResponse(
        provider="volcengine",
        session_id=str(request.interview_session_id),
        status="ready",
    )


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
    )


def _build_greeting(
    *, target_title: str, target_company: str, language: str
) -> str:
    """用于生成数字人进入房间后的第一句欢迎语。"""
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
    """用于根据 session 语言判断豆包面试官是否应使用中文。"""
    normalized = language.strip().lower()
    return normalized.startswith("zh") or "chinese" in normalized or "中文" in language


async def _close_ws_policy_violation(websocket: WebSocket, reason: str) -> None:
    """用于关闭WebSocket策略违规。"""
    await websocket.close(code=_WS_POLICY_VIOLATION, reason=reason)


async def _authorize_voice_session_ws(
    websocket: WebSocket,
    *,
    session_id: int,
    db: Session,
) -> InterviewSession | None:
    """用于鉴权语音会话WebSocket。"""
    token = websocket.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
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


def _build_volcengine_system_role(
    *,
    target_title: str,
    target_company: str,
    language: str,
    difficulty: str,
    jd_text: str,
    resume_text: str = "",
    interview_history: str = "",
    interview_plan: str = "",
) -> str:
    """用于构建火山引擎 O 版本的 system_role。"""
    return _render_interviewer_prompt(
        target_title=target_title,
        target_company=target_company,
        language=language,
        difficulty=difficulty,
        jd_text=jd_text[:_VOLCENGINE_JD_CONTEXT_CHARS],
        interview_plan=interview_plan[:_VOLCENGINE_PLAN_CONTEXT_CHARS],
        resume_text=resume_text[:_VOLCENGINE_RESUME_CONTEXT_CHARS],
        interview_history=interview_history[:_VOLCENGINE_HISTORY_CONTEXT_CHARS],
    ).strip()[:_VOLCENGINE_SYSTEM_ROLE_MAX_CHARS]


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


@router.websocket("/voice-session/{session_id}")
async def voice_session_ws(
    websocket: WebSocket,
    session_id: int,
    db: Session = Depends(get_db),
):
    """用于在前端和火山引擎之间代理实时语音 WebSocket 连接。"""
    interview_session = await _authorize_voice_session_ws(
        websocket,
        session_id=session_id,
        db=db,
    )
    if interview_session is None:
        return

    await websocket.accept()
    logger.info("Voice WebSocket accepted for interview_session_id=%s", session_id)
    service = VolcengineVoiceService()
    if not service.is_configured():
        logger.warning("Voice WebSocket closed because Volcengine is not configured")
        await websocket.send_json({"type": "error", "message": "火山引擎未配置"})
        await websocket.close()
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

        system_role = _build_volcengine_system_role(
            target_title=interview_session.target_title or "目标岗位",
            target_company=interview_session.target_company or "目标公司",
            language=interview_session.language,
            difficulty=interview_session.difficulty,
            jd_text=interview_session.jd_text or "",
            resume_text=resume_text,
            interview_history=_build_interview_history(existing_turns),
            interview_plan=_build_interview_plan_context(interview_session.plan_json),
        )
        if not existing_turns:
            greeting = _build_greeting(
                target_title=interview_session.target_title or "",
                target_company=interview_session.target_company or "",
                language=interview_session.language,
            )

    try:
        def persist_message(role: str, text: str) -> None:
            """用于持久化语音面试消息。"""
            record_voice_interview_message(
                db=db,
                session_id=session_id,
                role=role,
                text=text,
            )

        await service.proxy_session(
            client_ws=websocket,
            system_role=system_role,
            greeting=greeting,
            on_text_message=persist_message,
        )
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.exception("Volcengine voice proxy error")
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass

