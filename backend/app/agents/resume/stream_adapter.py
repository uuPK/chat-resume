"""用于承接 Resume Agent 的模型流适配策略。"""

from __future__ import annotations

import inspect
from collections.abc import AsyncGenerator
from typing import Any

from pi_agent_core import AgentContext, AssistantMessage, ToolCall
from pi_agent_core.types import StreamFn


class ResumeReActStreamAdapter:
    """用于把模型单轮响应规整为 ReAct 的一次一个工具调用。"""

    def __init__(self, stream_fn: StreamFn):
        """保存底层 stream 函数，并透传测试所需属性。"""
        self._stream_fn = stream_fn

    def __getattr__(self, name: str) -> Any:
        """透传底层 stream 函数的统计属性。"""
        return getattr(self._stream_fn, name)

    async def __call__(
        self,
        model: Any,
        context: AgentContext,
        options: Any,
    ) -> Any:
        """调用底层模型流，并过滤为单轮最多一个工具调用。"""
        response = self._stream_fn(model, context, options)
        if inspect.isawaitable(response):
            response = await response
        if not isinstance(response, dict):
            return response

        events = response.get("events")
        result = response.get("result")
        if events is None or result is None:
            return response

        return {
            **response,
            "events": self._single_tool_events(events),
            "result": self._single_tool_result(result),
        }

    async def _single_tool_events(self, events: Any) -> AsyncGenerator[Any, None]:
        """过滤流式事件中同一 assistant 响应的第二个及后续工具调用。"""
        async for event in events:
            normalized = self._single_tool_event(event)
            if normalized is not None:
                yield normalized

    def _single_tool_result(self, result: Any) -> Any:
        """返回一个可调用函数，用于产出已裁剪的最终 assistant message。"""

        async def get_result() -> Any:
            """用于延迟读取底层完整结果并裁剪工具调用。"""
            message = result()
            if inspect.isawaitable(message):
                message = await message
            if isinstance(message, AssistantMessage):
                return self._single_tool_message(message)
            return message

        return get_result

    @classmethod
    def _single_tool_event(cls, event: Any) -> Any | None:
        """对单个流式事件裁剪工具调用。"""
        event_type = str(getattr(event, "type", "") or "")
        if event_type.startswith("toolcall_") and not cls._is_first_tool_event(event):
            return None

        if hasattr(event, "partial") and isinstance(event.partial, AssistantMessage):
            return event.model_copy(update={"partial": cls._single_tool_message(event.partial)})
        if hasattr(event, "message") and isinstance(event.message, AssistantMessage):
            return event.model_copy(update={"message": cls._single_tool_message(event.message)})
        if hasattr(event, "error") and isinstance(event.error, AssistantMessage):
            return event.model_copy(update={"error": cls._single_tool_message(event.error)})
        return event

    @staticmethod
    def _is_first_tool_event(event: Any) -> bool:
        """判断当前 toolcall 流式事件是否属于本轮第一个工具调用。"""
        partial = getattr(event, "partial", None)
        if not isinstance(partial, AssistantMessage):
            return True
        content_index = getattr(event, "content_index", None)
        if not isinstance(content_index, int):
            return True
        tool_indexes = [
            index for index, block in enumerate(partial.content) if isinstance(block, ToolCall)
        ]
        return bool(tool_indexes) and content_index == tool_indexes[0]

    @staticmethod
    def _single_tool_message(message: AssistantMessage) -> AssistantMessage:
        """保留文本和首个工具调用，丢弃同一轮后续工具调用。"""
        seen_tool = False
        content: list[Any] = []
        for block in message.content:
            if not isinstance(block, ToolCall):
                content.append(block)
                continue
            if seen_tool:
                continue
            seen_tool = True
            content.append(block)
        return message.model_copy(update={"content": content})
