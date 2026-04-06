"""
轻量 Agent Runtime

负责通用的 Agent 执行循环：
- 构造消息
- 渲染系统提示词
- 调用 LLM
- 执行工具并回填结果
- 产出统一的非流式 / 流式结果
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional

from .chat_service import ChatService
from app.prompts import AgentPromptSpec


ToolExecutor = Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]
PromptContextBuilder = Callable[[Dict[str, Any]], Dict[str, Any]]


@dataclass(slots=True)
class AgentDefinition:
    """描述一个具体业务 Agent 的最小配置。"""

    prompt_spec: AgentPromptSpec
    tools_schema: List[Dict[str, Any]]
    tool_executor: ToolExecutor
    prompt_context_builder: PromptContextBuilder
    max_iterations: int = 6


class AgentRuntime:
    """轻量通用运行时，不包含具体业务规则。"""

    def __init__(self, chat_service: Optional[ChatService] = None):
        self.chat_service = chat_service or ChatService()

    async def run(
        self,
        agent: AgentDefinition,
        user_message: str,
        context: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """执行一次完整 Agent 循环并返回最终结果。"""
        messages = self._build_messages(user_message, conversation_history)
        executed_tools: List[Dict[str, Any]] = []
        final_text = ""

        for _ in range(agent.max_iterations):
            message = await self._next_message(agent, messages, context)
            messages.append(message)

            if not message.get("tool_calls"):
                final_text = message.get("content") or "已完成处理。"
                break

            tool_events = self._execute_tool_calls(agent, message["tool_calls"], context)
            executed_tools.extend(tool_events["executed_tools"])
            messages.extend(tool_events["tool_messages"])

        return {
            "content": final_text,
            "tool_calls": executed_tools,
            "context": context,
        }

    async def run_stream(
        self,
        agent: AgentDefinition,
        user_message: str,
        context: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Iterable[Dict[str, Any]]:
        """按阶段输出 Agent 执行事件。"""
        messages = self._build_messages(user_message, conversation_history)
        executed_tools: List[Dict[str, Any]] = []

        for _ in range(agent.max_iterations):
            message = await self._next_message(agent, messages, context)
            messages.append(message)

            if not message.get("tool_calls"):
                final_text = message.get("content") or "已完成处理。"
                async for chunk in self._stream_text(final_text):
                    yield {
                        "content": chunk,
                        "tool_calls": executed_tools,
                        "context": None,
                        "done": False,
                    }
                return

            tool_events = self._execute_tool_calls(agent, message["tool_calls"], context)
            executed_tools.extend(tool_events["executed_tools"])
            messages.extend(tool_events["tool_messages"])

            for stream_event in tool_events["stream_events"]:
                yield {
                    "content": "",
                    "tool_calls": executed_tools,
                    "context": context,
                    "done": False,
                    **stream_event,
                }

    def _build_messages(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]],
    ) -> List[Dict[str, Any]]:
        messages: List[Dict[str, Any]] = []
        if conversation_history:
            messages.extend(conversation_history[-6:])
        messages.append({"role": "user", "content": user_message})
        return messages

    async def _next_message(
        self,
        agent: AgentDefinition,
        messages: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        prompt_context = agent.prompt_context_builder(context)
        system_prompt = agent.prompt_spec.render(**prompt_context)
        defaults = agent.prompt_spec.model_defaults
        response = await self.chat_service.chat_completion(
            messages=messages,
            system_prompt=system_prompt,
            tools=agent.tools_schema,
            temperature=defaults.get("temperature", 0.3),
            max_tokens=defaults.get("max_tokens", 1500),
            stream=False,
        )
        return response["choices"][0]["message"]

    def _execute_tool_calls(
        self,
        agent: AgentDefinition,
        tool_calls: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        executed_tools: List[Dict[str, Any]] = []
        tool_messages: List[Dict[str, Any]] = []
        stream_events: List[Dict[str, Any]] = []

        for tool_call in tool_calls:
            tool_result = agent.tool_executor(tool_call, context)
            executed_tools.append(
                {
                    "name": tool_result["tool_name"],
                    "result": tool_result["display_message"] or "执行完成",
                }
            )
            tool_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": json.dumps(tool_result["result"], ensure_ascii=False),
                }
            )
            stream_events.append(
                {
                    "qr_images": [tool_result["qr_image"]] if tool_result["qr_image"] else [],
                }
            )

        return {
            "executed_tools": executed_tools,
            "tool_messages": tool_messages,
            "stream_events": stream_events,
        }

    async def _stream_text(self, text: str, chunk_size: int = 24):
        for i in range(0, len(text), chunk_size):
            yield text[i : i + chunk_size]
            await asyncio.sleep(0.02)
