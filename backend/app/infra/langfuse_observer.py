"""
Helpers for mirroring agent runs into Langfuse traces.
"""

from __future__ import annotations

import logging
from typing import Any

from app.infra.langfuse_setup import get_langfuse_client

logger = logging.getLogger(__name__)


class LangfuseRunObserver:
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
        self.client = get_langfuse_client()
        self.run_id = run_id
        self.agent_type = agent_type
        self.run_kind = run_kind
        self.user_id = user_id
        self.input_text = input_text
        self.metadata = dict(metadata or {})
        self.trace_url: str | None = None
        self._root_cm: Any | None = None
        self._root_observation: Any | None = None
        self._pending_llm_request: dict[str, Any] | None = None
        self._pending_tool_calls: dict[str, dict[str, Any]] = {}

    @property
    def enabled(self) -> bool:
        return self.client is not None

    def __enter__(self) -> "LangfuseRunObserver":
        if not self.enabled:
            return self
        self._root_cm = self.client.start_as_current_observation(
            name=f"{self.agent_type}:{self.run_kind}",
            as_type="agent",
            input=self.input_text,
            metadata={
                "run_id": self.run_id,
                "agent_type": self.agent_type,
                "run_kind": self.run_kind,
                **self.metadata,
            },
            end_on_exit=False,
        )
        self._root_observation = self._root_cm.__enter__()
        try:
            self.trace_url = self.client.get_trace_url()
        except Exception:
            self.trace_url = None
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if not self.enabled or self._root_cm is None:
            return
        self._root_cm.__exit__(exc_type, exc, tb)

    def finish(self, output: Any, *, metadata: dict[str, Any] | None = None) -> None:
        if not self.enabled or self._root_observation is None:
            return
        try:
            update_kwargs: dict[str, Any] = {"output": output}
            if metadata:
                update_kwargs["metadata"] = {
                    **(self.metadata or {}),
                    **metadata,
                }
            self._root_observation.update(**update_kwargs)
            self._root_observation.end()
        except Exception as exc:
            logger.warning("Langfuse finish failed run_id=%s error=%s", self.run_id, exc)

    def fail(self, error: str, *, metadata: dict[str, Any] | None = None) -> None:
        if not self.enabled or self._root_observation is None:
            return
        try:
            payload_metadata = {"run_id": self.run_id, **(metadata or {})}
            self._root_observation.update(
                output={"error": error},
                level="ERROR",
                status_message=error,
                metadata=payload_metadata,
            )
            self._root_observation.end()
        except Exception as exc:
            logger.warning("Langfuse fail failed run_id=%s error=%s", self.run_id, exc)

    def on_runtime_event(self, event: dict[str, Any]) -> None:
        if not self.enabled:
            return
        try:
            if event.get("prompt_rendered") or event.get("event_type") == "prompt_rendered":
                self._record_prompt_rendered(event)
            elif event.get("llm_request") or event.get("event_type") == "llm_request":
                self._pending_llm_request = event
            elif event.get("llm_response") or event.get("event_type") == "llm_response":
                self._record_llm_response(event)
            elif event.get("tool_pending") or event.get("event_type") == "tool_call":
                self._cache_tool_call(event)
            elif (
                event.get("tool_confirmed")
                or event.get("tool_rejected")
                or event.get("tool_call_failed")
                or event.get("event_type") == "tool_result"
            ):
                self._record_tool_result(event)
        except Exception as exc:
            logger.warning("Langfuse runtime event failed run_id=%s error=%s", self.run_id, exc)

    def _record_prompt_rendered(self, event: dict[str, Any]) -> None:
        with self.client.start_as_current_observation(
            name="prompt-rendered",
            as_type="span",
            input={"user_message_preview": event.get("user_message_preview")},
            output=event.get("system_prompt"),
            metadata={"agent_name": event.get("agent_name"), "run_id": self.run_id},
        ):
            return

    def _record_llm_response(self, event: dict[str, Any]) -> None:
        request = self._pending_llm_request or {}
        usage = event.get("usage") if isinstance(event.get("usage"), dict) else None
        metadata = {
            "run_id": self.run_id,
            "agent_name": event.get("agent_name") or request.get("agent_name"),
            "latency_ms": event.get("latency_ms"),
            "tool_call_count": event.get("tool_call_count"),
            "finish_reason": event.get("finish_reason"),
        }
        with self.client.start_as_current_observation(
            name="llm-call",
            as_type="generation",
            model=event.get("model") or request.get("model"),
            input=request.get("messages"),
            output=event.get("response_content") or event.get("content"),
            metadata=metadata,
            model_parameters=request.get("params"),
            usage_details=usage,
        ):
            pass
        self._pending_llm_request = None

    def _cache_tool_call(self, event: dict[str, Any]) -> None:
        call_id = event.get("call_id")
        cache_key = str(call_id or event.get("tool_name") or len(self._pending_tool_calls))
        self._pending_tool_calls[cache_key] = {
            "tool_name": event.get("tool_name"),
            "tool_input": event.get("tool_input"),
            "tool_call": event.get("tool_call"),
            "diff_summary": event.get("diff_summary"),
        }

    def _record_tool_result(self, event: dict[str, Any]) -> None:
        call_id = event.get("call_id")
        cache_key = str(call_id or event.get("tool_name") or "")
        pending = self._pending_tool_calls.pop(cache_key, {})
        success = True
        if event.get("tool_rejected") or event.get("tool_call_failed"):
            success = False
        if event.get("event_type") == "tool_result":
            success = bool(event.get("success", False))
        with self.client.start_as_current_observation(
            name=f"tool:{event.get('tool_name') or pending.get('tool_name') or 'unknown'}",
            as_type="tool",
            input=pending.get("tool_input") or pending.get("tool_call"),
            output=event.get("result"),
            metadata={
                "run_id": self.run_id,
                "call_id": call_id,
                "success": success,
                "display_message": event.get("display_message"),
                "diff_summary": pending.get("diff_summary"),
                "latency_ms": event.get("latency_ms"),
            },
            level="DEFAULT" if success else "ERROR",
            status_message=event.get("display_message"),
        ):
            pass
