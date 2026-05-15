"""用于集中管理简历 Agent 会话生命周期、公开事件和恢复落库。"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, cast

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.runtime.harness import AgentHarness
from app.services.domain import ResumeService
from app.services.errors import ServiceNotFoundError, ServicePermissionError
from app.state import AgentSessionStore
from app.types.stream import ResumeStreamEvent

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
_MODULE_TO_SECTION = {
    "personal": "personal_info",
    "education": "education",
    "work": "work_experience",
    "projects": "projects",
    "skills": "skills",
}


@dataclass(frozen=True)
class ResumeAgentStreamInput:
    """用于承载一次简历 Agent 流式会话的应用层输入。"""

    message: str
    resume_id: int
    user_id: int
    request_id: str | None
    chat_history: list[dict[str, str]] = field(default_factory=list)
    visible_modules: list[str] = field(default_factory=list)
    agent_type: str = "resume"
    is_interview: bool = False


@dataclass(frozen=True)
class ResumeAgentSessionContext:
    """用于承载一次可运行的简历 Agent 会话上下文。"""

    session_id: str
    store: AgentSessionStore
    harness: AgentHarness
    resume_service: ResumeService
    resume_content: dict[str, Any]
    original_resume: dict[str, Any]
    conversation_history: list[dict[str, str]]
    allowed_sections: set[str]


class ResumeAgentSessionCoordinator:
    """用于封装简历 Agent session 创建、公开事件、恢复和落库规则。"""

    def __init__(self, db: Session, store: AgentSessionStore | None = None):
        """用于初始化会话协调器依赖。"""
        self.db = db
        self.store = store or AgentSessionStore(db)

    def prepare_stream_session(
        self,
        *,
        request: ResumeAgentStreamInput,
        session_id: str,
    ) -> ResumeAgentSessionContext:
        """用于创建一次流式会话并返回运行所需上下文。"""
        self.ensure_stream_supported(request)
        resume_service = ResumeService(self.db)
        resume = self.get_resume_for_user(
            resume_service,
            resume_id=request.resume_id,
            user_id=request.user_id,
        )
        resume_content = self.load_filtered_resume_content(
            resume,
            request.visible_modules,
        )
        conversation_history = (
            []
            if self.should_ignore_history_for_request(request.message)
            else request.chat_history
        )
        harness = AgentHarness(self.db, session_store=self.store)
        harness.create_resume_session(
            session_id=session_id,
            user_id=request.user_id,
            resume_id=request.resume_id,
            user_message=request.message,
            visible_modules=request.visible_modules,
        )
        return ResumeAgentSessionContext(
            session_id=session_id,
            store=self.store,
            harness=harness,
            resume_service=resume_service,
            resume_content=resume_content,
            original_resume=deepcopy(resume_content),
            conversation_history=conversation_history,
            allowed_sections=set(resume_content.keys()),
        )

    def resume_paused_session(
        self,
        *,
        session_id: str,
        user_id: int,
    ) -> dict[str, Any]:
        """用于恢复因工具确认中断而暂停的简历 Agent session。"""
        session = self.store.get_session(session_id)
        if not session or session.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} 不存在",
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

        resume_service = ResumeService(self.db)
        resume = self.get_resume_for_user(
            resume_service,
            resume_id=session.resume_id,
            user_id=user_id,
        )
        metadata = (
            session.metadata_json if isinstance(session.metadata_json, dict) else {}
        )
        visible_modules = metadata.get("visible_modules")
        filtered_resume = self.load_filtered_resume_content(
            resume,
            visible_modules if isinstance(visible_modules, list) else [],
        )
        original_resume = deepcopy(filtered_resume)

        result = AgentHarness(self.db, session_store=self.store).resume_session(
            session_id=session_id,
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
            self.persist_resume_if_changed(
                resume_service,
                resume_id=session.resume_id,
                latest_resume_content=latest_resume_content,
                original_resume=original_resume,
            )

        return {
            "ok": True,
            "session_id": session_id,
            "applied": bool(result.get("applied")),
            "message": result["message"],
            "resume_content": latest_resume_content,
        }

    def replay_public_events(
        self,
        *,
        session_id: str,
        user_id: int,
        after_sequence: int,
    ) -> list[ResumeStreamEvent]:
        """用于按 SSE cursor 回放指定 session 的公开流事件。"""
        session = self.store.get_session(session_id)
        if not session or session.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} 不存在",
            )
        replayed: list[ResumeStreamEvent] = []
        for event in self.store.list_stream_events(
            session_id,
            after_sequence=after_sequence,
        ):
            payload = event.payload if isinstance(event.payload, dict) else {}
            replay_payload = dict(payload)
            replay_payload.pop("log_context", None)
            replay_payload["event_id"] = f"{session_id}:{event.sequence}"
            replayed.append(cast(ResumeStreamEvent, replay_payload))
        return replayed

    def record_public_event(
        self,
        *,
        store: AgentSessionStore,
        session_id: str,
        event: ResumeStreamEvent,
    ) -> ResumeStreamEvent:
        """用于给公开 SSE 事件分配 cursor 并写入事件日志。"""
        payload = dict(event)
        stored = store.append_stream_event(session_id=session_id, payload=payload)
        payload["event_id"] = f"{session_id}:{stored.sequence}"
        return cast(ResumeStreamEvent, payload)

    @staticmethod
    def ensure_stream_supported(request: ResumeAgentStreamInput) -> None:
        """用于兼容旧字段并拒绝已迁移的面试入口。"""
        requested = (request.agent_type or "").strip().lower()
        if requested == "resume":
            return
        if requested in {"interview", "interviewer"} or request.is_interview:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="面试聊天入口已下线，请使用 /api/interviews 结构化面试链路。",
            )
        return

    @staticmethod
    def should_ignore_history_for_request(message: str) -> bool:
        """用于识别应直接基于当前简历回答的问题。"""
        normalized = (message or "").strip()
        return any(keyword in normalized for keyword in _RESUME_SNAPSHOT_KEYWORDS)

    @staticmethod
    def filter_resume_by_visible_modules(
        resume_content: dict[str, Any],
        visible_modules: list[str],
    ) -> dict[str, Any]:
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

    @staticmethod
    def get_resume_for_user(
        resume_service: ResumeService,
        *,
        resume_id: int,
        user_id: int,
    ):
        """用于统一读取并校验当前用户可访问的简历。"""
        try:
            return resume_service.get_for_user(
                resume_id,
                user_id,
                not_found_message="简历不存在",
                permission_message="没有权限访问此简历",
            )
        except ServiceNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc
        except ServicePermissionError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(exc),
            ) from exc

    @staticmethod
    def dump_resume_content(resume: Any) -> dict[str, Any]:
        """用于把 ORM 简历内容安全收窄成可编辑字典。"""
        return cast(
            dict[str, Any],
            resume.content if isinstance(resume.content, dict) else {},
        )

    def load_filtered_resume_content(
        self,
        resume: Any,
        visible_modules: list[str],
    ) -> dict[str, Any]:
        """用于读取简历内容并按可见模块裁剪上下文。"""
        return self.filter_resume_by_visible_modules(
            self.dump_resume_content(resume),
            visible_modules,
        )

    @staticmethod
    def persist_resume_if_changed(
        resume_service: ResumeService,
        *,
        resume_id: int,
        latest_resume_content: dict[str, Any] | None,
        original_resume: dict[str, Any],
    ) -> None:
        """用于只在内容确实变化时落库存储结构化简历。"""
        if latest_resume_content is None or latest_resume_content == original_resume:
            return
        resume_service.update(resume_id, {"content": latest_resume_content})


__all__ = [
    "ResumeAgentSessionContext",
    "ResumeAgentSessionCoordinator",
    "ResumeAgentStreamInput",
]
