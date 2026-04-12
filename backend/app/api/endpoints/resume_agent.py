"""
智能聊天API端点模块

提供与 AI Agent 聊天交互的 API 端点，包括简历优化和模拟面试。
"""

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Dict, Any, cast
from copy import deepcopy
from uuid import uuid4
from app.agents.definitions import InterviewerAgent, ResumeAgent
from app.agents.runtime import AgentHarness, confirmation_manager
from app.agents.state import AgentSessionStore
from app.services.core import ResumeService
from app.services.llm import ChatService
from app.core.database import get_db
from app.api.deps import get_current_user
import json
import logging

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
    """聊天请求模型"""

    message: str
    resume_id: int
    chat_history: list = []  # 聊天历史，可选
    visible_modules: list[str] = []
    agent_type: str = "resume"
    is_interview: bool = False  # 兼容旧前端字段


class ConfirmToolRequest(BaseModel):
    session_id: str
    call_id: str
    confirmed: bool


class ResumeSessionRequest(BaseModel):
    session_id: str


def _resolve_agent_type(chat_request: ChatRequest) -> str:
    requested = (chat_request.agent_type or "").strip().lower()
    if requested == "resume":
        return "resume"
    if requested in {"interview", "interviewer"}:
        return "interview"
    if chat_request.is_interview:
        return "interview"
    return "resume"


def _should_ignore_history_for_request(message: str) -> bool:
    normalized = (message or "").strip()
    return any(keyword in normalized for keyword in _RESUME_SNAPSHOT_KEYWORDS)


_MODULE_TO_SECTION = {
    "personal": "personal_info",
    "education": "education",
    "work": "work_experience",
    "projects": "projects",
    "skills": "skills",
}


def _filter_resume_by_visible_modules(resume_content: Dict[str, Any], visible_modules: list[str]) -> Dict[str, Any]:
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


def _truncate_text(value: Any, max_length: int = 220) -> str:
    if isinstance(value, list):
        # highlights / achievements 等 [{id, text}, ...] 结构 → 提取纯文本
        if value and all(isinstance(i, dict) and "text" in i for i in value):
            text = " | ".join(i["text"] for i in value if i.get("text"))
        else:
            text = json.dumps(value, ensure_ascii=False)
    elif not isinstance(value, str):
        text = json.dumps(value, ensure_ascii=False)
    else:
        text = value
    text = text.replace("\n", " ")
    return text if len(text) <= max_length else text[: max_length - 1] + "…"


def _extract_item_label(item: Any) -> str:
    if not isinstance(item, dict):
        return _truncate_text(item, 80)
    for key in ("name", "company", "school", "title", "position", "category"):
        value = item.get(key)
        if value:
            return str(value)
    return item.get("id", "未命名项")


def _build_object_changes(section: str, before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    for key in sorted(set(before.keys()) | set(after.keys())):
        if before.get(key) != after.get(key):
            changes.append(
                {
                    "section": section,
                    "op": "update",
                    "field": key,
                    "before": _truncate_text(before.get(key, "空")),
                    "after": _truncate_text(after.get(key, "空")),
                }
            )
    return changes


def _build_list_changes(section: str, before: list[Any], after: list[Any]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    before_map = {
        str(item.get("id")): item
        for item in before
        if isinstance(item, dict) and item.get("id")
    }
    after_map = {
        str(item.get("id")): item
        for item in after
        if isinstance(item, dict) and item.get("id")
    }

    for item_id in sorted(set(before_map.keys()) | set(after_map.keys())):
        before_item = before_map.get(item_id)
        after_item = after_map.get(item_id)
        item_label = _extract_item_label(after_item or before_item)
        if before_item is None and after_item is not None:
            changes.append(
                {
                    "section": section,
                    "op": "add",
                    "item_id": item_id,
                    "item_label": item_label,
                    "field": "item",
                    "before": "空",
                    "after": _truncate_text(after_item),
                }
            )
            continue
        if before_item is not None and after_item is None:
            changes.append(
                {
                    "section": section,
                    "op": "remove",
                    "item_id": item_id,
                    "item_label": item_label,
                    "field": "item",
                    "before": _truncate_text(before_item),
                    "after": "空",
                }
            )
            continue
        if before_item != after_item and before_item and after_item:
            for field in sorted(set(before_item.keys()) | set(after_item.keys())):
                if before_item.get(field) != after_item.get(field):
                    changes.append(
                        {
                            "section": section,
                            "op": "update",
                            "item_id": item_id,
                            "item_label": item_label,
                            "field": field,
                            "before": _truncate_text(before_item.get(field, "空")),
                            "after": _truncate_text(after_item.get(field, "空")),
                        }
                    )

    if not changes and before != after:
        changes.append(
            {
                "section": section,
                "op": "update",
                "field": "list",
                "before": _truncate_text(before),
                "after": _truncate_text(after),
            }
        )
    return changes


def _build_proposal_patch(before: Dict[str, Any], after: Dict[str, Any]) -> dict[str, Any]:
    changes: list[dict[str, Any]] = []
    for key in sorted(set(before.keys()) | set(after.keys())):
        before_value = before.get(key)
        after_value = after.get(key)
        if before_value == after_value:
            continue
        if isinstance(before_value, dict) and isinstance(after_value, dict):
            changes.extend(_build_object_changes(key, before_value, after_value))
        elif isinstance(before_value, list) and isinstance(after_value, list):
            changes.extend(_build_list_changes(key, before_value, after_value))
        else:
            changes.append(
                {
                    "section": key,
                    "op": "update",
                    "field": "value",
                    "before": _truncate_text(before_value if before_value is not None else "空"),
                    "after": _truncate_text(after_value if after_value is not None else "空"),
                }
            )
    return {"changes": changes}


@router.post("/chat/stream")
async def chat_with_resume_stream(
    chat_request: ChatRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """与AI助手进行流式聊天，基于用户真实简历内容"""

    agent_type = _resolve_agent_type(chat_request)
    logger.info("=== 流式聊天API被调用 ===")
    logger.info("收到请求 - agent_type: %s", agent_type)
    logger.info("用户消息: %s", chat_request.message)

    agent = ResumeAgent() if agent_type == "resume" else InterviewerAgent()
    session_id = uuid4().hex if agent_type == "resume" else None
    confirmation_queue = confirmation_manager.create(session_id) if session_id else None

    async def generate_stream():
        try:
            if session_id:
                yield f"data: {json.dumps({'session_id': session_id, 'content': '', 'done': False}, ensure_ascii=False)}\n\n"

            # 获取用户真实简历数据
            resume_service = ResumeService(db)
            resume = resume_service.get_by_id(chat_request.resume_id)

            if not resume:
                error_data = {"error": "简历不存在", "done": True}
                yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
                return

            logger.debug(f"Stream Resume ID: {chat_request.resume_id}")
            logger.debug(f"Stream Resume owner_id: {resume.owner_id}")
            logger.debug(f"Stream Current user ID: {current_user['id']}")

            if resume.owner_id != current_user["id"]:
                error_data = {
                    "error": f"没有权限访问此简历 (简历所有者: {resume.owner_id}, 当前用户: {current_user['id']})",
                    "done": True,
                }
                yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
                return

            resume_dict: Dict[str, Any] = cast(
                Dict[str, Any],
                resume.content if isinstance(resume.content, dict) else {},
            )
            resume_dict = _filter_resume_by_visible_modules(
                resume_dict,
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
            harness = AgentHarness(db) if session_id else None

            if harness and session_id:
                harness.create_resume_session(
                    session_id=session_id,
                    user_id=current_user["id"],
                    resume_id=chat_request.resume_id,
                    user_message=chat_request.message,
                    visible_modules=chat_request.visible_modules,
                )

            if agent_type == "resume":
                assert isinstance(agent, ResumeAgent)
                assert harness is not None
                event_stream = harness.run_resume_stream(
                    session_id=session_id,
                    agent=agent,
                    user_message=chat_request.message,
                    resume_content=resume_dict,
                    conversation_history=conversation_history,
                    confirmation_queue=confirmation_queue,
                    allowed_sections=set(resume_dict.keys()),
                )
            else:
                event_stream = agent.chat_stream(
                    user_message=chat_request.message,
                    resume_content=resume_dict,
                    conversation_history=conversation_history,
                )

            async for event in event_stream:
                if event.get("resume_content") is not None:
                    latest_resume_content = event["resume_content"]
                # 过滤掉值为 None 的键，减少传输体积
                payload = {k: v for k, v in event.items() if v is not None}
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

            if (
                agent_type == "resume"
                and latest_resume_content is not None
                and latest_resume_content != original_resume
            ):
                resume_service.update(
                    chat_request.resume_id,
                    {"content": latest_resume_content},
                )
                proposal_patch = _build_proposal_patch(original_resume, latest_resume_content)
                resume_service.create_proposal(
                    resume_id=chat_request.resume_id,
                    user_message=chat_request.message,
                    proposed_content=latest_resume_content,
                    summary="已通过逐步确认完成的简历修改",
                    section=(
                        proposal_patch["changes"][0]["section"]
                        if proposal_patch.get("changes")
                        else None
                    ),
                    proposed_patch=proposal_patch,
                    tool_calls=[],
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
            yield f"data: {json.dumps(end_data, ensure_ascii=False)}\n\n"

        except Exception as e:
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
    request: ConfirmToolRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """接收前端对某个工具调用的确认或拒绝信号。"""
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
    if session.status != "waiting_confirmation" or pending_call_id != request.call_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="当前 session 没有匹配的待确认工具调用",
        )

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
            "message": "确认结果已记录，但当前流式连接已结束，需要恢复 session 后继续执行",
        }

    await queue.put(request.confirmed)
    return {"ok": True}


@router.post("/chat/resume-session")
async def resume_agent_session(
    request: ResumeSessionRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """恢复已暂停的 resume agent session。"""
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
    resume = resume_service.get_by_id(session.resume_id)
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="简历不存在",
        )
    if resume.owner_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限访问此简历",
        )

    resume_dict: Dict[str, Any] = cast(
        Dict[str, Any],
        resume.content if isinstance(resume.content, dict) else {},
    )
    metadata = session.metadata_json if isinstance(session.metadata_json, dict) else {}
    visible_modules = metadata.get("visible_modules")
    filtered_resume = _filter_resume_by_visible_modules(
        resume_dict,
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
    proposal_patch = None
    if result.get("applied") and latest_resume_content != original_resume:
        resume_service.update(
            session.resume_id,
            {"content": latest_resume_content},
        )
        proposal_patch = _build_proposal_patch(original_resume, latest_resume_content)
        user_message_event = store.get_latest_event(
            request.session_id,
            event_type="user_message",
        )
        user_message = (
            user_message_event.payload.get("content")
            if user_message_event and isinstance(user_message_event.payload, dict)
            else "恢复执行已确认的简历修改"
        )
        resume_service.create_proposal(
            resume_id=session.resume_id,
            user_message=user_message,
            proposed_content=latest_resume_content,
            summary=result["message"],
            section=(
                proposal_patch["changes"][0]["section"]
                if proposal_patch.get("changes")
                else None
            ),
            proposed_patch=proposal_patch,
            tool_calls=[],
        )

    return {
        "ok": True,
        "session_id": request.session_id,
        "applied": bool(result.get("applied")),
        "message": result["message"],
        "resume_content": latest_resume_content,
        "proposal_patch": proposal_patch,
    }


@router.get("/status")
async def get_ai_status():
    """获取AI服务状态"""
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


@router.get("/boss/status")
async def get_boss_status(
    current_user: dict = Depends(get_current_user),
):
    """获取Boss直聘登录状态"""
    try:
        from app.agents.tools.resume_tools.boss_client import get_login_status

        return get_login_status()
    except Exception as e:
        logger.error(f"获取Boss状态失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取状态失败: {str(e)}",
        )
