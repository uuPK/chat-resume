"""用于把 Agent 运行事件同步到 LangSmith 追踪。"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from app.infra.config import settings
from app.infra.langsmith_setup import get_langsmith_client

logger = logging.getLogger(__name__)


class LangSmithRunObserver:
    """用于把一次 Agent 运行和内部 runtime 事件镜像到 LangSmith。"""

    def __init__(
        self,
        *,
        run_id: str,
        agent_type: str,
        run_kind: str,
        user_id: int,
        input_text: str | None,
        metadata: dict[str, Any] | None = None,
    ):
        """用于初始化当前对象。"""
        self.client = get_langsmith_client()
        self.run_id = run_id
        self.agent_type = agent_type
        self.run_kind = run_kind
        self.user_id = user_id
        self.input_text = input_text
        self.metadata = {
            "run_id": run_id,
            "agent_type": agent_type,
            "run_kind": run_kind,
            "user_id": user_id,
            "environment": settings.APP_ENV,
            **(metadata or {}),
        }
        self.tags = [
            "agent",
            f"agent:{agent_type}",
            f"kind:{run_kind}",
            f"env:{settings.APP_ENV}",
        ]
        self._trace_context: Any | None = None
        self._root_run_id = _stable_uuid(run_id)
        self._llm_run_id: UUID | None = None
        self._tool_run_ids: dict[str, UUID] = {}
        self._events: list[dict[str, Any]] = []
        self._event_index = 0

    @property
    def enabled(self) -> bool:
        """用于判断是否启用当前数据。"""
        return self.client is not None

    def __enter__(self) -> "LangSmithRunObserver":
        """用于进入当前上下文管理器。"""
        if not self.enabled:
            return self
        try:
            from langsmith import tracing_context

            self._trace_context = tracing_context(
                project_name=settings.LANGSMITH_PROJECT,
                tags=self.tags,
                metadata=self.metadata,
                enabled=True,
                client=self.client,
            )
            self._trace_context.__enter__()
        except Exception as exc:
            logger.warning(
                "LangSmith run start failed run_id=%s error=%s",
                self.run_id,
                exc,
            )
            self._trace_context = None
        self._create_root_run()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        """用于退出当前上下文管理器并收尾。"""
        if self._trace_context is None:
            return
        try:
            self._trace_context.__exit__(exc_type, exc, tb)
        except Exception as exit_exc:
            logger.warning(
                "LangSmith tracing context exit failed run_id=%s error=%s",
                self.run_id,
                exit_exc,
            )

    def finish(self, output: Any, *, metadata: dict[str, Any] | None = None) -> None:
        """用于完成当前数据。"""
        if not self.enabled:
            return
        self._update_run(
            self._root_run_id,
            outputs={"output": output},
            end_time=_utcnow(),
            events=self._events,
            extra={"metadata": {**self.metadata, **(metadata or {})}},
        )

    def fail(self, error: str, *, metadata: dict[str, Any] | None = None) -> None:
        """用于标记失败当前数据。"""
        if not self.enabled:
            return
        self._close_open_child_runs(error)
        self._update_run(
            self._root_run_id,
            error=error,
            end_time=_utcnow(),
            events=self._events,
            extra={"metadata": {**self.metadata, **(metadata or {})}},
        )

    def on_runtime_event(self, event: Mapping[str, Any]) -> None:
        """用于处理onruntime事件。"""
        if not self.enabled:
            return
        event_type = _event_type(event)
        self._record_event(event_type, event)
        if event.get("prompt_rendered"):
            self._create_prompt_run(event)
            return
        if event.get("llm_request"):
            self._create_llm_run(event)
            return
        if event.get("llm_response"):
            self._finish_llm_run(event)
            return
        if event.get("tool_pending"):
            self._create_tool_run(event)
            return
        if (
            event.get("tool_confirmed")
            or event.get("tool_rejected")
            or event.get("tool_call_failed")
            or _is_tool_result_event(event)
        ):
            self._finish_tool_run(event)

    def _create_root_run(self) -> None:
        """用于创建 LangSmith 顶层 Agent run。"""
        self._create_run(
            id=self._root_run_id,
            name=f"{self.agent_type}.{self.run_kind}",
            run_type="chain",
            inputs={"input": self.input_text},
            start_time=_utcnow(),
            tags=self.tags,
            extra={"metadata": self.metadata},
        )

    def _create_prompt_run(self, event: Mapping[str, Any]) -> None:
        """用于记录渲染后的系统提示词。"""
        run_id = self._child_run_id("prompt")
        system_prompt = str(event.get("system_prompt") or "")
        self._create_run(
            id=run_id,
            name="prompt.rendered",
            run_type="prompt",
            inputs={
                "system_prompt": system_prompt,
                "user_message_preview": event.get("user_message_preview"),
            },
            outputs={"prompt_chars": len(system_prompt)},
            start_time=_utcnow(),
            end_time=_utcnow(),
            parent_run_id=self._root_run_id,
            trace_id=self._root_run_id,
            tags=self.tags,
            extra={"metadata": self.metadata},
        )

    def _create_llm_run(self, event: Mapping[str, Any]) -> None:
        """用于记录一次模型请求。"""
        run_id = self._child_run_id(f"llm:{self._event_index}")
        self._llm_run_id = run_id
        self._create_run(
            id=run_id,
            name=f"model.{event.get('model') or 'unknown'}",
            run_type="llm",
            inputs={
                "messages": event.get("messages", []),
                "params": event.get("params", {}),
                "tool_names": event.get("tool_names", []),
            },
            start_time=_utcnow(),
            parent_run_id=self._root_run_id,
            trace_id=self._root_run_id,
            tags=[*self.tags, "runtime:pi-agent-core"],
            extra={"metadata": {**self.metadata, "model": event.get("model")}},
        )

    def _finish_llm_run(self, event: Mapping[str, Any]) -> None:
        """用于记录模型响应。"""
        if self._llm_run_id is None:
            return
        self._update_run(
            self._llm_run_id,
            outputs={
                "response": event.get("response_content"),
                "tool_call_count": event.get("tool_call_count"),
                "latency_ms": event.get("latency_ms"),
            },
            end_time=_utcnow(),
        )
        self._llm_run_id = None

    def _create_tool_run(self, event: Mapping[str, Any]) -> None:
        """用于记录一次等待确认的业务工具调用。"""
        call_id = _call_id(event)
        run_id = self._child_run_id(f"tool:{call_id}")
        self._tool_run_ids[call_id] = run_id
        self._create_run(
            id=run_id,
            name=f"tool.{event.get('tool_id') or event.get('tool_name') or 'unknown'}",
            run_type="tool",
            inputs={
                "call_id": call_id,
                "tool_input": event.get("tool_input"),
                "diff_summary": event.get("diff_summary"),
                "diff_items": event.get("diff_items", []),
            },
            start_time=_utcnow(),
            parent_run_id=self._root_run_id,
            trace_id=self._root_run_id,
            tags=self.tags,
            extra={
                "metadata": {
                    **self.metadata,
                    "call_id": call_id,
                    "tool_name": event.get("tool_name"),
                }
            },
        )

    def _finish_tool_run(self, event: Mapping[str, Any]) -> None:
        """用于结束工具 run；没有 preview 的只读工具会在这里创建即时 run。"""
        call_id = _call_id(event)
        run_id = self._tool_run_ids.get(call_id)
        if run_id is None:
            run_id = self._child_run_id(f"tool:{call_id}")
            self._tool_run_ids[call_id] = run_id
            self._create_run(
                id=run_id,
                name=f"tool.{event.get('tool_id') or event.get('tool_name') or 'unknown'}",
                run_type="tool",
                inputs={"call_id": call_id},
                start_time=_utcnow(),
                parent_run_id=self._root_run_id,
                trace_id=self._root_run_id,
                tags=self.tags,
                extra={"metadata": {**self.metadata, "call_id": call_id}},
            )
        error = None
        if event.get("tool_rejected"):
            error = "用户拒绝了此修改"
        if event.get("tool_call_failed"):
            error = str(event.get("display_message") or event.get("result") or "")
        self._update_run(
            run_id,
            outputs={
                "confirmed": event.get("tool_confirmed"),
                "rejected": event.get("tool_rejected"),
                "result": event.get("result"),
                "display_message": event.get("display_message"),
                "diff_summary": event.get("diff_summary"),
                "diff_items": event.get("diff_items", []),
            },
            error=error,
            end_time=_utcnow(),
        )
        self._tool_run_ids.pop(call_id, None)

    def _close_open_child_runs(self, error: str) -> None:
        """用于异常结束时收敛未关闭的子 run。"""
        if self._llm_run_id is not None:
            self._update_run(self._llm_run_id, error=error, end_time=_utcnow())
            self._llm_run_id = None
        for run_id in list(self._tool_run_ids.values()):
            self._update_run(run_id, error=error, end_time=_utcnow())
        self._tool_run_ids.clear()

    def _record_event(self, event_type: str, event: Mapping[str, Any]) -> None:
        """用于把 runtime event 作为顶层 run 的 timeline 事件保存。"""
        self._event_index += 1
        self._events.append(
            {
                "name": event_type,
                "time": _utcnow().isoformat(),
                "kwargs": _compact_event(event),
            }
        )

    def _child_run_id(self, key: str) -> UUID:
        """用于为同一 agent run 内的子 run 生成稳定 UUID。"""
        return uuid5(self._root_run_id, key)

    def _create_run(self, **kwargs: Any) -> None:
        """用于安全调用 LangSmith create_run，避免观测失败影响主流程。"""
        if self.client is None:
            return
        try:
            self.client.create_run(
                project_name=settings.LANGSMITH_PROJECT,
                **kwargs,
            )
        except Exception as exc:
            logger.warning(
                "LangSmith create_run failed run_id=%s error=%s",
                self.run_id,
                exc,
            )

    def _update_run(self, run_id: UUID, **kwargs: Any) -> None:
        """用于安全调用 LangSmith update_run，避免观测失败影响主流程。"""
        if self.client is None:
            return
        try:
            self.client.update_run(run_id, **kwargs)
        except Exception as exc:
            logger.warning(
                "LangSmith update_run failed run_id=%s child_id=%s error=%s",
                self.run_id,
                run_id,
                exc,
            )


def _stable_uuid(value: str) -> UUID:
    """用于把内部 run_id 转成 LangSmith 接受的 UUID。"""
    try:
        return UUID(value)
    except ValueError:
        return uuid5(NAMESPACE_URL, value)


def _utcnow() -> datetime:
    """用于返回 timezone-aware UTC 时间。"""
    return datetime.now(timezone.utc)


def _event_type(event: Mapping[str, Any]) -> str:
    """用于给未显式标注的 runtime event 推断类型。"""
    raw = event.get("event_type")
    if isinstance(raw, str) and raw:
        return raw
    for key in (
        "prompt_rendered",
        "llm_request",
        "llm_response",
        "tool_pending",
        "tool_confirmed",
        "tool_rejected",
        "tool_call_failed",
    ):
        if event.get(key):
            return key
    if _is_tool_result_event(event):
        return "tool_result"
    if event.get("content"):
        return "text_delta"
    return "runtime_event"


def _call_id(event: Mapping[str, Any]) -> str:
    """用于提取工具调用 ID，缺失时退化为稳定占位值。"""
    call_id = event.get("call_id")
    if isinstance(call_id, str) and call_id:
        return call_id
    tool_name = event.get("tool_name") or event.get("tool_id") or "unknown"
    return f"missing:{tool_name}"


def _is_tool_result_event(event: Mapping[str, Any]) -> bool:
    """用于识别只读工具完成事件。"""
    return bool(event.get("display_message") and event.get("result") is not None)


def _compact_event(event: Mapping[str, Any]) -> dict[str, Any]:
    """用于限制写入 LangSmith timeline 的 runtime event 体积。"""
    compact: dict[str, Any] = {}
    for key in (
        "event_type",
        "agent_name",
        "model",
        "call_id",
        "tool_id",
        "tool_name",
        "tool_display_name",
        "diff_summary",
        "display_message",
        "latency_ms",
        "tool_call_count",
        "done",
    ):
        value = event.get(key)
        if value is not None:
            compact[key] = _compact_value(value)
    content = event.get("content")
    if isinstance(content, str) and content:
        compact["content_preview"] = _preview(content)
    return compact


def _compact_value(value: Any) -> Any:
    """用于递归压缩日志值。"""
    if isinstance(value, str):
        return _preview(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [_compact_value(item) for item in value[:5]]
    if isinstance(value, dict):
        return {str(key): _compact_value(item) for key, item in list(value.items())[:8]}
    return _preview(value)


def _preview(value: Any, limit: int = 500) -> str:
    """用于生成单行预览文本。"""
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."
