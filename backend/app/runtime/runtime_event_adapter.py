"""用于隔离 runtime 事件发布和可见事件适配。"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from time import perf_counter
from typing import Any

from pi_agent_core import AgentContext, TextContent
from pi_agent_core.types import Message

from app.agents.resume.stream_events import (
    llm_request_event,
    llm_response_event,
    prompt_rendered_event,
    text_delta_event,
    tool_call_event,
    tool_call_failed_event,
    tool_confirmed_event,
    tool_pending_event,
    tool_rejected_event,
    tool_result_event,
)
from app.runtime.contracts import RuntimeEventCallback
from app.runtime.contracts import AgentDefinition
from app.runtime.openrouter_adapter import openrouter_chat_model_name
from app.types.stream import ResumeStreamEvent


class RuntimeEventPublisher:
    """用于集中生成和发布 runtime 可见事件。"""

    def __init__(self, chat_model_name: Callable[[], str] | None = None):
        """用于初始化 runtime 事件发布器的模型名来源。"""
        self._chat_model_name = chat_model_name or openrouter_chat_model_name

    @staticmethod
    def new_stream_state() -> dict[str, Any]:
        """用于创建一次 run_stream 的事件状态。"""
        return {
            "started_at": perf_counter(),
            "chunk_index": 0,
            "response_parts": [],
            "last_assistant_text": "",
            "confirmed_diff_items": [],
            "tool_profile": "",
            "tool_names": [],
            "unexpected_tool_call_names": set(),
            "prompt_chars": 0,
            "tool_call_count": 0,
            "visible_tool_call_ids": set(),
            "first_token_latency_ms": None,
            "usage": {},
            "confirmation_wait_ms": 0.0,
        }

    def llm_request(
        self,
        agent: AgentDefinition,
        context: AgentContext,
        prompts: list[Message],
        state: dict[str, Any],
    ) -> ResumeStreamEvent:
        """用于生成 LLM 请求事件。"""
        messages = [self.message_to_dict(message) for message in context.messages + prompts]
        tool_names: list[str | None] = [tool.name for tool in context.tools]
        return llm_request_event(
            agent_name=agent.prompt_spec.name,
            model=self._chat_model_name(),
            messages=[{"role": "system", "content": context.system_prompt}, *messages],
            params={
                "temperature": agent.prompt_spec.model_defaults.get("temperature", 0.3),
                "max_tokens": agent.prompt_spec.model_defaults.get("max_tokens", 1500),
            },
            tool_names=tool_names,
            tool_profile=str(state.get("tool_profile") or ""),
            prompt_chars=int(state.get("prompt_chars") or len(context.system_prompt)),
        )

    def llm_response(
        self,
        agent: AgentDefinition,
        state: dict[str, Any],
    ) -> ResumeStreamEvent:
        """用于生成 LLM 响应事件。"""
        return llm_response_event(
            agent_name=agent.prompt_spec.name,
            model=self._chat_model_name(),
            response_content="".join(state["response_parts"]),
            tool_call_count=int(state.get("tool_call_count") or 0),
            latency_ms=round((perf_counter() - state["started_at"]) * 1000, 2),
            first_token_latency_ms=state.get("first_token_latency_ms"),
            usage=state.get("usage") if isinstance(state.get("usage"), dict) else {},
            confirmation_wait_ms=float(state.get("confirmation_wait_ms") or 0.0),
        )

    @staticmethod
    def prompt_rendered(
        agent: AgentDefinition,
        system_prompt: str,
        user_message: str,
    ) -> ResumeStreamEvent:
        """用于生成 prompt rendered 事件。"""
        return prompt_rendered_event(
            agent_name=agent.prompt_spec.name,
            system_prompt=system_prompt,
            user_message_preview=str(user_message)[:1500],
        )

    @staticmethod
    def text_delta(content: str) -> ResumeStreamEvent:
        """用于生成文本增量事件。"""
        return text_delta_event(content=content)

    @staticmethod
    def tool_call_started(
        *,
        call_id: str,
        tool_name: str,
        tool_call: dict[str, Any],
        tool_input: dict[str, Any],
    ) -> ResumeStreamEvent:
        """用于生成工具开始事件。"""
        return tool_call_event(
            call_id=call_id,
            tool_id=tool_name,
            tool_call=tool_call,
            tool_display_name=tool_name,
            tool_input=tool_input,
            display_message=f"正在{tool_name}",
            tool_calls=[],
        )

    @staticmethod
    def tool_pending(
        *,
        call_id: str,
        tool_name: str,
        tool_call: dict[str, Any],
        tool_display_name: str,
        tool_input: dict[str, Any],
        diff_summary: str,
        diff_items: Any,
        tool_calls: list[dict[str, Any]],
    ) -> ResumeStreamEvent:
        """用于生成工具待确认事件。"""
        return tool_pending_event(
            call_id=call_id,
            tool_id=tool_name,
            tool_call=tool_call,
            tool_display_name=tool_display_name,
            tool_input=tool_input,
            diff_summary=diff_summary,
            diff_items=diff_items,
            tool_calls=tool_calls,
        )

    @staticmethod
    def tool_rejected(
        *,
        call_id: str,
        tool_name: str,
        tool_display_name: str,
        diff_summary: str,
        diff_items: Any,
        result: dict[str, Any],
        tool_calls: list[dict[str, Any]],
    ) -> ResumeStreamEvent:
        """用于生成工具拒绝事件。"""
        return tool_rejected_event(
            call_id=call_id,
            tool_id=tool_name,
            tool_display_name=tool_display_name,
            diff_summary=diff_summary,
            diff_items=diff_items,
            result=result,
            tool_calls=tool_calls,
        )

    @staticmethod
    def tool_result(
        *,
        call_id: str,
        tool_name: str,
        tool_display_name: str,
        tool_calls: list[dict[str, Any]],
        result: Any,
        display_message: str | None,
        context: dict[str, Any] | None,
    ) -> ResumeStreamEvent:
        """用于生成普通工具结果事件。"""
        return tool_result_event(
            call_id=call_id,
            tool_id=tool_name,
            tool_display_name=tool_display_name,
            tool_calls=tool_calls,
            result=result,
            display_message=display_message,
            context=context,
        )

    @staticmethod
    def tool_confirmed(
        *,
        call_id: str,
        tool_name: str,
        tool_display_name: str,
        tool_calls: list[dict[str, Any]],
        result: Any,
        display_message: str | None,
        diff_summary: str | None,
        diff_items: Any,
        context: dict[str, Any],
        qr_images: list[str],
    ) -> ResumeStreamEvent:
        """用于生成工具确认事件。"""
        return tool_confirmed_event(
            call_id=call_id,
            tool_id=tool_name,
            tool_display_name=tool_display_name,
            tool_calls=tool_calls,
            qr_images=qr_images,
            result=result,
            display_message=display_message,
            diff_summary=diff_summary,
            diff_items=diff_items,
            context=context,
        )

    @staticmethod
    def tool_call_failed(
        *,
        call_id: str,
        tool_name: str,
        tool_display_name: str,
        tool_calls: list[dict[str, Any]],
        result: Any,
        display_message: str | None,
    ) -> ResumeStreamEvent:
        """用于生成工具失败事件。"""
        return tool_call_failed_event(
            call_id=call_id,
            tool_id=tool_name,
            tool_display_name=tool_display_name,
            tool_calls=tool_calls,
            result=result,
            display_message=display_message,
        )

    async def publish(
        self,
        *,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        event: ResumeStreamEvent,
    ) -> None:
        """用于同时发布 runtime callback 和可选 SSE 队列事件。"""
        await publish_runtime_event(
            event_queue=event_queue,
            event_callback=event_callback,
            event=event,
        )

    def emit(
        self,
        event_callback: RuntimeEventCallback | None,
        event: ResumeStreamEvent,
    ) -> None:
        """用于向调用方 callback 发布 runtime 事件。"""
        emit_runtime_event(event_callback, event)

    @staticmethod
    def message_to_dict(message: Message) -> dict[str, Any]:
        """用于把 pi-agent-core 消息转换为可记录事件字段。"""
        role = getattr(message, "role", "unknown")
        content = RuntimeEventPublisher.assistant_text(message)
        return {"role": role, "content": content}

    @staticmethod
    def assistant_text(message: Any) -> str:
        """用于读取 assistant 文本块内容。"""
        parts = []
        for block in getattr(message, "content", []):
            if isinstance(block, TextContent):
                parts.append(block.text)
        return "".join(parts)


async def publish_runtime_event(
    *,
    event_queue: asyncio.Queue[Any] | None,
    event_callback: RuntimeEventCallback | None,
    event: ResumeStreamEvent,
) -> None:
    """用于同时发布 runtime callback 和可选 SSE 队列事件。"""
    emit_runtime_event(event_callback, event)
    if event_queue is not None:
        await event_queue.put(event)


def emit_runtime_event(
    event_callback: RuntimeEventCallback | None,
    event: ResumeStreamEvent,
) -> None:
    """用于向调用方 callback 发布 runtime 事件。"""
    if event_callback is not None:
        event_callback(event)


__all__ = ["RuntimeEventPublisher", "emit_runtime_event", "publish_runtime_event"]
