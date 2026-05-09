"""
智能聊天API端点模块

提供与 AI Agent 聊天交互的 API 端点，包括简历优化。
"""

import json
import logging
from copy import deepcopy
from typing import Any, Dict, cast
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.resume.agent import ResumeAgent
from app.entrypoints.http.deps import get_current_user
from app.infra.database import get_db
from app.infra.langfuse_observer import LangfuseRunObserver
from app.infra.request_context import log_context
from app.runtime.harness import AgentHarness
from app.runtime.permissions import confirmation_manager
from app.services.domain import ResumeService
from app.services.llm import ChatService
from app.state import AgentSessionStore

logger = logging.getLogger(__name__)

router = APIRouter()

_RESUME_SNAPSHOT_KEYWORDS = (
    "复述",
    "重复一遍",
    "当前简历",
    "现在的简历",
    "我的简历内容",
    "完整内容",
    "列出我的简历",
    "把我的简历写出来",
)


class ChatRequest(BaseModel):
    """用于承载简历 Agent 聊天请求体。"""

    message: str
    resume_id: int
    chat_history: list = []  # 聊天历史，可选
    visible_modules: list[str] = []
    agent_type: str = "resume"
    is_interview: bool = False  # 兼容旧前端字段；面试主链路已迁移到 /api/interviews


class ConfirmToolRequest(BaseModel):
    """用于承载工具确认结果。"""

    session_id: str
    call_id: str
    confirmed: bool


class ResumeSessionRequest(BaseModel):
    """用于承载暂停 session 的恢复请求。"""

    session_id: str


def _resolve_agent_type(chat_request: ChatRequest) -> str:
    """用于兼容旧字段并统一解析目标 agent 类型。"""
    requested = (chat_request.agent_type or "").strip().lower()
    if requested == "resume":
        return "resume"
    if requested in {"interview", "interviewer"}:
        return "interview"
    if chat_request.is_interview:
        return "interview"
    return "resume"


def _should_ignore_history_for_request(message: str) -> bool:
    """用于识别应直接基于当前简历回答的问题。"""
    normalized = (message or "").strip()
    return any(keyword in normalized for keyword in _RESUME_SNAPSHOT_KEYWORDS)


_MODULE_TO_SECTION = {
    "personal": "personal_info",
    "education": "education",
    "work": "work_experience",
    "projects": "projects",
    "skills": "skills",
}


def _filter_resume_by_visible_modules(
    resume_content: Dict[str, Any], visible_modules: list[str]
) -> Dict[str, Any]:
    """用于按前端可见模块裁剪传给 Agent 的简历内容。"""
    if not visible_modules:
        return resume_content

    allowed_sections = {
        _MODULE_TO_SECTION[module]
        for module in visible_modules
        if module in _MODULE_TO_SECTION
    }
    filtered = {}
    if "job_application" in resume_content:
        filtered["job_application"] = resume_content["job_application"]
    for section in allowed_sections:
        if section in resume_content:
            filtered[section] = resume_content[section]
    return filtered


def _get_resume_for_user(
    resume_service: ResumeService, *, resume_id: int, user_id: int
):
    """用于统一读取并校验当前用户可访问的简历。"""
    resume = resume_service.get_by_id(resume_id)
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="简历不存在",
        )
    if resume.owner_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限访问此简历",
        )
    return resume


def _dump_resume_content(resume: Any) -> Dict[str, Any]:
    """用于把 ORM 简历内容安全收窄成可编辑字典。"""
    return cast(
        Dict[str, Any],
        resume.content if isinstance(resume.content, dict) else {},
    )


def _load_filtered_resume_content(
    resume: Any, visible_modules: list[str]
) -> Dict[str, Any]:
    """用于读取简历内容并按可见模块裁剪上下文。"""
    return _filter_resume_by_visible_modules(
        _dump_resume_content(resume),
        visible_modules,
    )


def _persist_resume_if_changed(
    resume_service: ResumeService,
    *,
    resume_id: int,
    latest_resume_content: Any,
    original_resume: Dict[str, Any],
) -> None:
    """用于只在内容确实变化时落库存储结构化简历。"""
    if latest_resume_content is None or latest_resume_content == original_resume:
        return
    resume_service.update(resume_id, {"content": latest_resume_content})


@router.post("/chat/stream")
async def chat_with_resume_stream(
    request: Request,
    chat_request: ChatRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于以 SSE 方式驱动一次完整的简历 Agent 流式对话。"""

    agent_type = _resolve_agent_type(chat_request)
    if agent_type != "resume":
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="面试聊天入口已下线，请使用 /api/interviews 结构化面试链路。",
        )
    logger.info(
        "resume_agent.stream.requested",
        extra={
            "agent_type": agent_type,
            "resume_id": chat_request.resume_id,
            "user_id": current_user["id"],
            "message_chars": len(chat_request.message or ""),
        },
    )

    agent = ResumeAgent()
    session_id = uuid4().hex
    run_id = uuid4().hex
    confirmation_queue = confirmation_manager.create(session_id)
    request_id = getattr(request.state, "request_id", None)

    async def generate_stream():
        with log_context(request_id=request_id, session_id=session_id):
            final_content_parts: list[str] = []
            observer = LangfuseRunObserver(
                run_id=run_id,
                agent_type="resume",
                run_kind="chat_stream",
                user_id=current_user["id"],
                input_text=chat_request.message,
                metadata={
                    "session_id": session_id,
                    "resume_id": chat_request.resume_id,
                    "request_id": request_id,
                },
            )
            logger.info(
                "Resume agent stream started resume_id=%s user_id=%s",
                chat_request.resume_id,
                current_user["id"],
            )
            try:
                if session_id:
                    session_payload = {
                        "session_id": session_id,
                        "content": "",
                        "done": False,
                    }
                    yield (
                        f"data: {json.dumps(session_payload, ensure_ascii=False)}\n\n"
                    )

                # 获取用户真实简历数据
                resume_service = ResumeService(db)
                try:
                    resume = _get_resume_for_user(
                        resume_service,
                        resume_id=chat_request.resume_id,
                        user_id=current_user["id"],
                    )
                except HTTPException as exc:
                    error_data = {"error": str(exc.detail), "done": True}
                    yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
                    return

                logger.debug(f"Stream Resume ID: {chat_request.resume_id}")
                logger.debug(f"Stream Resume owner_id: {resume.owner_id}")
                logger.debug(f"Stream Current user ID: {current_user['id']}")

                resume_dict = _load_filtered_resume_content(
                    resume,
                    chat_request.visible_modules,
                )

                logger.debug("流式接口 agent_type=%s", agent_type)
                latest_resume_content = None
                original_resume = deepcopy(resume_dict)
                conversation_history = (
                    []
                    if _should_ignore_history_for_request(chat_request.message)
                    else chat_request.chat_history
                )
                harness = AgentHarness(db)
                harness.create_resume_session(
                    session_id=session_id,
                    user_id=current_user["id"],
                    resume_id=chat_request.resume_id,
                    user_message=chat_request.message,
                    visible_modules=chat_request.visible_modules,
                )
                with observer:
                    event_stream = harness.run_resume_stream(
                        session_id=session_id,
                        agent=agent,
                        user_message=chat_request.message,
                        resume_content=resume_dict,
                        conversation_history=conversation_history,
                        confirmation_queue=confirmation_queue,
                        allowed_sections=set(resume_dict.keys()),
                        event_callback=observer.on_runtime_event,
                        user_id=current_user["id"],
                    )

                    async for event in event_stream:
                        if event.get("internal_only"):
                            continue
                        if event.get("resume_content") is not None:
                            latest_resume_content = event["resume_content"]
                        if event.get("content"):
                            final_content_parts.append(event["content"])
                        # 过滤掉值为 None 的键，减少传输体积
                        payload = {k: v for k, v in event.items() if v is not None}
                        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

                    observer.finish("".join(final_content_parts))

                _persist_resume_if_changed(
                    resume_service,
                    resume_id=chat_request.resume_id,
                    latest_resume_content=latest_resume_content,
                    original_resume=original_resume,
                )

                # 发送结束标记，附带最终简历内容用于刷新预览
                end_data: Dict[str, Any] = {
                    "content": "",
                    "qr_images": [],
                    "tool_calls": [],
                    "done": True,
                }
                if latest_resume_content is not None:
                    end_data["resume_content"] = latest_resume_content
                logger.info("Resume agent stream completed")
                yield f"data: {json.dumps(end_data, ensure_ascii=False)}\n\n"

            except Exception as e:
                logger.exception("Resume agent stream failed")
                observer.fail(str(e))
                error_data = {"error": f"AI服务暂时不可用: {str(e)}", "done": True}
                yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
            finally:
                if session_id:
                    confirmation_manager.remove(session_id)

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        },
    )


@router.post("/chat/confirm-tool")
async def confirm_tool(
    http_request: Request,
    request: ConfirmToolRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于接收前端对单个工具调用的确认或拒绝结果。"""
    with log_context(
        request_id=getattr(http_request.state, "request_id", None),
        session_id=request.session_id,
        tool_call_id=request.call_id,
    ):
        store = AgentSessionStore(db)
        session = store.get_session(request.session_id)
        if not session or session.user_id != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {request.session_id} 不存在",
            )

        latest_pending = store.get_latest_event(
            request.session_id,
            event_type="tool_call_previewed",
        )
        pending_call_id = (
            latest_pending.payload.get("call_id")
            if latest_pending and isinstance(latest_pending.payload, dict)
            else None
        )
        if pending_call_id != request.call_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="当前 session 没有匹配的待确认工具调用",
            )

        if session.status != "waiting_confirmation":
            return {
                "ok": True,
                "duplicate": True,
                "message": "该工具确认已处理",
            }

        queue = confirmation_manager.get(request.session_id)
        if queue is None:
            store.append_confirmation_event(
                session_id=request.session_id,
                call_id=request.call_id,
                confirmed=request.confirmed,
                tool_name=(
                    latest_pending.payload.get("tool_name")
                    if latest_pending and isinstance(latest_pending.payload, dict)
                    else None
                ),
                active_stream=False,
            )
            store.update_status(
                request.session_id,
                "paused",
                current_step=request.call_id,
            )
            return {
                "ok": False,
                "resumable": True,
                "message": (
                    "确认结果已记录，但当前流式连接已结束，需要恢复 session 后继续执行"
                ),
            }

        store.update_status(
            request.session_id,
            "running",
            clear_current_step=True,
        )
        await queue.put(request.confirmed)
        logger.info(
            "Resume agent tool confirmation received confirmed=%s", request.confirmed
        )
        return {"ok": True}


@router.post("/chat/resume-session")
async def resume_agent_session(
    http_request: Request,
    request: ResumeSessionRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于恢复因确认中断而暂停的简历 Agent session。"""
    with log_context(
        request_id=getattr(http_request.state, "request_id", None),
        session_id=request.session_id,
    ):
        store = AgentSessionStore(db)
        session = store.get_session(request.session_id)
        if not session or session.user_id != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {request.session_id} 不存在",
            )
        if session.task_type != "resume_optimization":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="当前 session 不是简历优化任务",
            )
        if session.resume_id is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="当前 session 未关联简历",
            )

        resume_service = ResumeService(db)
        resume = _get_resume_for_user(
            resume_service,
            resume_id=session.resume_id,
            user_id=current_user["id"],
        )
        metadata = (
            session.metadata_json if isinstance(session.metadata_json, dict) else {}
        )
        visible_modules = metadata.get("visible_modules")
        filtered_resume = _load_filtered_resume_content(
            resume,
            visible_modules if isinstance(visible_modules, list) else [],
        )
        original_resume = deepcopy(filtered_resume)

        harness = AgentHarness(db, session_store=store)
        result = harness.resume_session(
            session_id=request.session_id,
            resume_content=filtered_resume,
            allowed_sections=set(filtered_resume.keys()),
        )
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=result["message"],
            )

        latest_resume_content = result["resume_content"]
        if result.get("applied"):
            _persist_resume_if_changed(
                resume_service,
                resume_id=session.resume_id,
                latest_resume_content=latest_resume_content,
                original_resume=original_resume,
            )

        logger.info(
            "Resume agent session resumed applied=%s", bool(result.get("applied"))
        )
        return {
            "ok": True,
            "session_id": request.session_id,
            "applied": bool(result.get("applied")),
            "message": result["message"],
            "resume_content": latest_resume_content,
        }


@router.get("/status")
async def get_ai_status():
    """用于返回当前 AI 聊天服务是否已完成配置。"""
    try:
        chat_service = ChatService()
        # 简单的状态检查
        if chat_service.api_key and chat_service.api_key.strip():
            return {
                "service": "openrouter",
                "status": "connected",
                "is_configured": True,
            }
        else:
            return {
                "service": "mock",
                "status": "not_configured",
                "is_configured": False,
            }
    except Exception:
        return {"service": "mock", "status": "error", "is_configured": False}
