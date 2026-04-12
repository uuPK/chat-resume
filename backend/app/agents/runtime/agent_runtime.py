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

from app.services.llm.chat_service import ChatService
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
    max_history_messages: int = 20


class AgentRuntime:
    """轻量通用运行时，不包含具体业务规则。"""

    def __init__(self, chat_service: Optional[ChatService] = None):
        self.chat_service = chat_service or ChatService()
        self.max_recoverable_tool_errors = 2

    async def run(
        self,
        agent: AgentDefinition,
        user_message: str,
        context: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """执行一次完整 Agent 循环并返回最终结果。"""
        messages = self._build_messages(user_message, conversation_history, agent.max_history_messages)
        executed_tools: List[Dict[str, Any]] = []
        final_text = ""
        recoverable_error_counts: Dict[str, int] = {}

        for _ in range(agent.max_iterations):
            message = await self._next_message(agent, messages, context)
            message = self._limit_tool_calls(message)
            messages.append(message)

            if not message.get("tool_calls"):
                final_text = message.get("content") or ""
                break

            tool_events = self._execute_tool_calls(
                agent,
                message["tool_calls"],
                context,
                recoverable_error_counts=recoverable_error_counts,
            )
            executed_tools.extend(tool_events["executed_tools"])
            messages.extend(tool_events["tool_messages"])
            if tool_events.get("retry_exhausted_message"):
                final_text = tool_events["retry_exhausted_message"]
                break

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
        messages = self._build_messages(user_message, conversation_history, agent.max_history_messages)
        executed_tools: List[Dict[str, Any]] = []
        recoverable_error_counts: Dict[str, int] = {}

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
                tool_calls_list = self._limit_tool_call_list(tool_calls_list)
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
                            "tool_call": tc,
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
                            retry_exhausted_message = self._record_recoverable_tool_error(
                                tc,
                                tool_result,
                                recoverable_error_counts,
                            )
                            tool_messages.append({
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "content": json.dumps(
                                    tool_result["result"], ensure_ascii=False
                                ),
                            })
                            if self._is_tool_failure(tool_result):
                                yield {
                                    "content": "",
                                    "tool_call_failed": True,
                                    "call_id": tc["id"],
                                    "tool_name": tool_result["tool_name"],
                                    "tool_calls": executed_tools,
                                    "result": tool_result["result"],
                                    "display_message": tool_result.get("display_message"),
                                    "done": False,
                                }
                                if retry_exhausted_message:
                                    yield {
                                        "content": retry_exhausted_message,
                                        "tool_calls": executed_tools,
                                        "context": None,
                                        "done": False,
                                    }
                                    return
                                continue
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
                        tool_events = self._execute_tool_calls(
                            agent,
                            [tc],
                            context,
                            recoverable_error_counts=recoverable_error_counts,
                        )
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
                        if tool_events.get("retry_exhausted_message"):
                            yield {
                                "content": tool_events["retry_exhausted_message"],
                                "tool_calls": executed_tools,
                                "context": None,
                                "done": False,
                            }
                            return

                messages.extend(tool_messages)
                continue

            if accumulated_content:
                # 纯文本轮次：agent 完成
                messages.append({"role": "assistant", "content": accumulated_content})
                return

            # 空响应，终止
            break

    @staticmethod
    def _limit_tool_call_list(tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if len(tool_calls) <= 1:
            return tool_calls
        logger.info(
            "Agent returned %s tool calls in one round; only the first will be executed",
            len(tool_calls),
        )
        return tool_calls[:1]

    def _limit_tool_calls(self, message: Dict[str, Any]) -> Dict[str, Any]:
        tool_calls = message.get("tool_calls")
        if not isinstance(tool_calls, list) or len(tool_calls) <= 1:
            return message
        limited = dict(message)
        limited["tool_calls"] = self._limit_tool_call_list(tool_calls)
        return limited

    def _build_messages(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]],
        max_history_messages: int = 20,
    ) -> List[Dict[str, Any]]:
        messages: List[Dict[str, Any]] = []
        if conversation_history:
            messages.extend(conversation_history[-max_history_messages:])
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
        user_message = messages[-1].get("content", "") if messages else ""
        logger.info(
            "AgentRuntime request agent=%s system_prompt_preview=%r user_message_preview=%r",
            agent.prompt_spec.name,
            system_prompt[:1500],
            str(user_message)[:1500],
        )
        base_max_tokens = defaults.get("max_tokens", 1500)
        max_tokens = base_max_tokens

        for attempt in range(2):
            response = await self.chat_service.chat_completion(
                messages=messages,
                system_prompt=system_prompt,
                tools=agent.tools_schema,
                temperature=defaults.get("temperature", 0.3),
                max_tokens=max_tokens,
                stream=False,
            )
            choice = response["choices"][0]
            message = dict(choice["message"])
            message["content"] = ChatService._coerce_content_text(message.get("content"))
            finish_reason = choice.get("finish_reason")
            has_tool_calls = bool(message.get("tool_calls"))

            if message.get("content") or has_tool_calls or finish_reason != "length" or attempt > 0:
                break

            max_tokens = min(max(base_max_tokens * 2, 512), 2048)
            logger.warning(
                "AgentRuntime empty truncated response agent=%s; retrying with max_tokens=%s",
                agent.prompt_spec.name,
                max_tokens,
            )

        logger.info(
            "AgentRuntime response agent=%s finish_reason=%s content_preview=%r tool_calls=%s",
            agent.prompt_spec.name,
            choice.get("finish_reason"),
            (message.get("content") or "")[:300],
            bool(message.get("tool_calls")),
        )
        return message

    def _execute_tool_calls(
        self,
        agent: AgentDefinition,
        tool_calls: List[Dict[str, Any]],
        context: Dict[str, Any],
        recoverable_error_counts: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        executed_tools: List[Dict[str, Any]] = []
        tool_messages: List[Dict[str, Any]] = []
        stream_events: List[Dict[str, Any]] = []
        retry_exhausted_message: Optional[str] = None
        error_counts = recoverable_error_counts if recoverable_error_counts is not None else {}

        for tool_call in tool_calls:
            tool_result = agent.tool_executor(tool_call, context)
            retry_exhausted_message = self._record_recoverable_tool_error(
                tool_call,
                tool_result,
                error_counts,
            )
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
            stream_event = {
                "qr_images": [tool_result["qr_image"]] if tool_result["qr_image"] else [],
            }
            if self._is_tool_failure(tool_result):
                stream_event.update(
                    {
                        "tool_call_failed": True,
                        "call_id": tool_call["id"],
                        "tool_name": tool_result["tool_name"],
                        "result": tool_result["result"],
                        "display_message": tool_result.get("display_message"),
                    }
                )
            stream_events.append(
                stream_event
            )
            if retry_exhausted_message:
                break

        return {
            "executed_tools": executed_tools,
            "tool_messages": tool_messages,
            "stream_events": stream_events,
            "retry_exhausted_message": retry_exhausted_message,
        }

    @staticmethod
    def _is_tool_failure(tool_result: Dict[str, Any]) -> bool:
        result = tool_result.get("result")
        return isinstance(result, dict) and result.get("success") is False

    @staticmethod
    def _tool_error(tool_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        result = tool_result.get("result")
        if not isinstance(result, dict):
            return None
        error = result.get("error")
        return error if isinstance(error, dict) else None

    def _record_recoverable_tool_error(
        self,
        tool_call: Dict[str, Any],
        tool_result: Dict[str, Any],
        recoverable_error_counts: Dict[str, int],
    ) -> Optional[str]:
        error = self._tool_error(tool_result)
        if not error or not error.get("recoverable"):
            return None

        tool_name = tool_call.get("function", {}).get("name") or tool_result.get("tool_name")
        error_type = error.get("type") or "unknown"
        key = f"{tool_name}:{error_type}"
        recoverable_error_counts[key] = recoverable_error_counts.get(key, 0) + 1
        if recoverable_error_counts[key] <= self.max_recoverable_tool_errors:
            return None

        message = error.get("message") or tool_result.get("display_message") or "工具调用参数持续失败"
        return f"工具调用连续失败，已停止自动重试。失败原因：{message}"
