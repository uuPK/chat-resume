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
import logging
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

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
        confirmation_queue: Optional[asyncio.Queue] = None,
    ) -> Iterable[Dict[str, Any]]:
        """真正的上游流式转发：
        - tool_call 轮次：积累完整响应后执行工具，期间发送工具进度事件
        - 文本轮次：直接将上游 SSE delta token 转发给客户端
        - confirmation_queue 不为 None 时，每个工具调用前暂停等待用户确认
        """
        messages = self._build_messages(user_message, conversation_history)
        executed_tools: List[Dict[str, Any]] = []

        for _ in range(agent.max_iterations):
            prompt_context = agent.prompt_context_builder(context)
            system_prompt = agent.prompt_spec.render(**prompt_context)
            defaults = agent.prompt_spec.model_defaults

            accumulated_content = ""
            # index -> {id, type, function: {name, arguments}}
            accumulated_tool_calls: Dict[int, Dict[str, Any]] = {}

            async for delta in self.chat_service.chat_completion_stream_deltas(
                messages=messages,
                system_prompt=system_prompt,
                tools=agent.tools_schema,
                temperature=defaults.get("temperature", 0.3),
                max_tokens=defaults.get("max_tokens", 1500),
            ):
                # 同时积累 content 和 tool_calls（模型可能先输出分析文本再调用工具）
                chunk = delta.get("content") or ""
                if chunk:
                    accumulated_content += chunk
                    yield {
                        "content": chunk,
                        "tool_calls": executed_tools,
                        "context": None,
                        "done": False,
                    }

                for tc_delta in (delta.get("tool_calls") or []):
                    idx = tc_delta.get("index", 0)
                    if idx not in accumulated_tool_calls:
                        accumulated_tool_calls[idx] = {
                            "id": "",
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        }
                    tc = accumulated_tool_calls[idx]
                    if tc_delta.get("id"):
                        tc["id"] = tc_delta["id"]
                    func = tc_delta.get("function") or {}
                    tc["function"]["name"] += func.get("name") or ""
                    tc["function"]["arguments"] += func.get("arguments") or ""

            # --- 本轮 delta 读完，按是否有 tool_calls 决定后续 ---

            if accumulated_tool_calls:
                tool_calls_list = list(accumulated_tool_calls.values())
                logger.debug(f"[run_stream] accumulated tool_calls: {json.dumps(tool_calls_list, ensure_ascii=False)}")
                messages.append({
                    "role": "assistant",
                    "content": accumulated_content or None,
                    "tool_calls": tool_calls_list,
                })

                tool_messages: List[Dict[str, Any]] = []

                for tc in tool_calls_list:
                    if confirmation_queue is not None:
                        # ---- 需要用户确认：在副本上预执行拿 diff，不修改真实 context ----
                        preview_context = {"resume_content": deepcopy(context.get("resume_content"))}
                        preview_result = agent.tool_executor(tc, preview_context)
                        diff_summary = preview_result.get("display_message") or "执行完成"

                        # 发送 pending 事件，前端展示 diff 并等待用户操作
                        yield {
                            "content": "",
                            "tool_pending": True,
                            "call_id": tc["id"],
                            "tool_name": preview_result["tool_name"],
                            "diff_summary": diff_summary,
                            "tool_calls": executed_tools,
                            "done": False,
                        }

                        # 挂起，等待确认信号（超时 5 分钟视为拒绝）
                        try:
                            confirmed = await asyncio.wait_for(
                                confirmation_queue.get(), timeout=300
                            )
                        except asyncio.TimeoutError:
                            confirmed = False

                        if not confirmed:
                            # 用户拒绝：context 未被修改，无需回滚
                            tool_messages.append({
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "content": json.dumps(
                                    {"error": "用户拒绝了此修改", "success": False},
                                    ensure_ascii=False,
                                ),
                            })
                            yield {
                                "content": "",
                                "tool_rejected": True,
                                "call_id": tc["id"],
                                "tool_name": preview_result["tool_name"],
                                "tool_calls": executed_tools,
                                "done": False,
                            }
                        else:
                            # 用户确认：在真实 context 上执行
                            tool_result = agent.tool_executor(tc, context)
                            executed_tools.append({
                                "name": tool_result["tool_name"],
                                "result": diff_summary,
                            })
                            tool_messages.append({
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "content": json.dumps(
                                    tool_result["result"], ensure_ascii=False
                                ),
                            })
                            qr_images = (
                                [tool_result["qr_image"]]
                                if tool_result.get("qr_image")
                                else []
                            )
                            yield {
                                "content": "",
                                "tool_confirmed": True,
                                "call_id": tc["id"],
                                "tool_name": tool_result["tool_name"],
                                "tool_calls": executed_tools,
                                "qr_images": qr_images,
                                "context": context,
                                "done": False,
                            }
                    else:
                        # ---- 无需确认：原有逻辑直接执行 ----
                        tool_events = self._execute_tool_calls(agent, [tc], context)
                        executed_tools.extend(tool_events["executed_tools"])
                        tool_messages.extend(tool_events["tool_messages"])
                        for stream_event in tool_events["stream_events"]:
                            yield {
                                "content": "",
                                "tool_calls": executed_tools,
                                "context": context,
                                "done": False,
                                **stream_event,
                            }

                messages.extend(tool_messages)
                continue

            if accumulated_content:
                # 纯文本轮次：agent 完成
                messages.append({"role": "assistant", "content": accumulated_content})
                return

            # 空响应，终止
            break

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

