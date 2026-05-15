"""用于封装 PiAgentRuntime 的 ReAct 单轮调度。"""

from __future__ import annotations

import asyncio
import inspect
from itertools import count
from time import perf_counter
from typing import Any, AsyncGenerator

from pi_agent_core import (
    AgentContext,
    AgentLoopConfig,
    AssistantMessage,
    SimpleStreamOptions,
    TextContent,
    ToolCall,
    ToolExecutionStartEvent,
    ToolResultMessage,
    UserMessage,
)
from pi_agent_core.types import Message, StreamFn

from app.runtime.contracts import AgentDefinition, RuntimeEventCallback
from app.runtime.message_conversion import convert_resume_messages_to_llm
from app.runtime.openrouter_adapter import build_openrouter_loop_config
from app.runtime.runtime_event_adapter import RuntimeEventPublisher
from app.runtime.tool_execution_pipeline import ToolExecutionPipeline
from app.runtime.trace_recorder import DefaultTraceRecorder


class _ReActStreamFn:
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
            """读取完整 assistant message 并裁剪多余工具调用。"""
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


class ReActTurnRunner:
    """用于执行 ReAct loop 的模型调用、工具 roundtrip 和文本发布。"""

    def __init__(
        self,
        *,
        stream_fn: StreamFn,
        tool_pipeline: ToolExecutionPipeline,
        event_publisher: RuntimeEventPublisher,
        trace_recorder: DefaultTraceRecorder,
    ):
        """用于初始化 ReAct turn runner 的可注入依赖。"""
        self.stream_fn = _ReActStreamFn(stream_fn)
        self.tool_pipeline = tool_pipeline
        self.event_publisher = event_publisher
        self.trace_recorder = trace_recorder

    async def produce_stream_events(
        self,
        *,
        agent: AgentDefinition,
        run_id: str,
        pi_context: AgentContext,
        prompts: list[Message],
        config: AgentLoopConfig,
        context: dict[str, Any],
        confirmation_queue: asyncio.Queue | None,
        event_queue: asyncio.Queue[Any],
        event_callback: RuntimeEventCallback | None,
        state: dict[str, Any],
        executed_tools: list[dict[str, Any]],
        done_sentinel: object,
    ) -> None:
        """用于生产 stream 事件并在结束时发布 LLM response 和 sentinel。"""
        try:
            await self.run_loop(
                agent=agent,
                run_id=run_id,
                pi_context=pi_context,
                prompts=prompts,
                config=config,
                context=context,
                confirmation_queue=confirmation_queue,
                event_queue=event_queue,
                event_callback=event_callback,
                state=state,
                executed_tools=executed_tools,
            )
        finally:
            response_event = self.event_publisher.llm_response(agent, state)
            self.trace_recorder.llm_response(agent, run_id, response_event)
            await self.event_publisher.publish(
                event_queue=event_queue,
                event_callback=event_callback,
                event=response_event,
            )
            await event_queue.put(done_sentinel)

    async def run_loop(
        self,
        *,
        agent: AgentDefinition,
        run_id: str,
        pi_context: AgentContext,
        prompts: list[Message],
        config: AgentLoopConfig,
        context: dict[str, Any],
        confirmation_queue: asyncio.Queue | None,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        state: dict[str, Any],
        executed_tools: list[dict[str, Any]],
    ) -> None:
        """显式执行 Claude Code 风格的 ReAct 循环。"""
        messages = [*pi_context.messages, *prompts]
        iteration_limit = (
            max(1, agent.max_iterations)
            if agent.max_iterations is not None
            else None
        )
        for turn_index in count():
            if iteration_limit is not None and turn_index >= iteration_limit:
                self.trace_recorder.max_iterations_reached(agent, run_id, state)
                return
            llm_context = await self._llm_context_for_turn(
                pi_context=pi_context,
                messages=messages,
                config=config,
            )
            request_event = self.event_publisher.llm_request(agent, llm_context, [], state)
            self.trace_recorder.llm_request(agent, run_id, request_event)
            await self.event_publisher.publish(
                event_queue=event_queue,
                event_callback=event_callback,
                event=request_event,
            )
            assistant_message, text_deltas = await self._stream_assistant_turn(
                agent=agent,
                run_id=run_id,
                llm_context=llm_context,
                config=config,
                event_queue=event_queue,
                event_callback=event_callback,
                state=state,
            )
            messages.append(assistant_message)
            if assistant_message.stop_reason in ("error", "aborted"):
                return

            tool_calls = self._assistant_tool_calls(assistant_message)
            if not tool_calls:
                await self._publish_text_deltas(
                    agent=agent,
                    run_id=run_id,
                    event_queue=event_queue,
                    event_callback=event_callback,
                    state=state,
                    text_deltas=text_deltas,
                )
                return
            if text_deltas:
                await self._publish_text_deltas(
                    agent=agent,
                    run_id=run_id,
                    event_queue=event_queue,
                    event_callback=event_callback,
                    state=state,
                    text_deltas=text_deltas,
                )
            tool_call = tool_calls[0]
            if len(tool_calls) > 1:
                self.trace_recorder.extra_tool_calls_ignored(
                    agent,
                    run_id,
                    tool_call.name,
                    len(tool_calls),
                )
            tool_result = await self._execute_react_tool(
                agent=agent,
                run_id=run_id,
                tool_call=tool_call,
                context=context,
                confirmation_queue=confirmation_queue,
                event_queue=event_queue,
                event_callback=event_callback,
                state=state,
                executed_tools=executed_tools,
            )
            messages.append(tool_result)

    def build_loop_inputs(
        self,
        *,
        agent: AgentDefinition,
        user_message: str,
        context: dict[str, Any],
        conversation_history: list[dict[str, str]] | None,
        run_id: str,
        confirmation_queue: asyncio.Queue | None,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        executed_tools: list[dict[str, Any]],
        stream_state: dict[str, Any],
    ) -> tuple[AgentContext, list[Message], AgentLoopConfig]:
        """用于构建 ReAct loop 的初始上下文、用户 prompt 和 provider 配置。"""
        context["conversation_history"] = conversation_history or []
        context["confirmed_diff_items"] = stream_state["confirmed_diff_items"]
        tool_profile = self.tool_pipeline.tool_profile(agent, context)
        context["tool_profile"] = tool_profile
        tools_schema = self.tool_pipeline.profiled_tool_schemas(agent, tool_profile)
        context["available_tool_names"] = self.tool_pipeline.tool_names_from_schemas(
            tools_schema
        )
        prompt_context = agent.prompt_context_builder(context)
        system_prompt = agent.prompt_spec.render(**prompt_context)
        tools = self.tool_pipeline.build_tools(
            agent=agent,
            tools_schema=tools_schema,
            context=context,
            confirmation_queue=confirmation_queue,
            event_queue=event_queue,
            event_callback=event_callback,
            run_id=run_id,
            executed_tools=executed_tools,
            stream_state=stream_state,
        )
        pi_context = AgentContext(
            system_prompt=system_prompt,
            messages=self.history_messages(
                conversation_history,
                agent.max_history_messages,
            ),
            tools=tools,
        )
        stream_state["tool_profile"] = tool_profile
        stream_state["tool_names"] = self.tool_pipeline.tool_names_from_schemas(
            tools_schema
        )
        stream_state["prompt_chars"] = len(system_prompt)
        prompts: list[Message] = [UserMessage(content=[TextContent(text=user_message)])]
        config = build_openrouter_loop_config(
            agent,
            convert_to_llm=convert_resume_messages_to_llm,
        )
        return pi_context, prompts, config

    @staticmethod
    def history_messages(
        conversation_history: list[dict[str, str]] | None,
        max_history_messages: int,
    ) -> list[Message]:
        """用于把业务历史消息转换为 pi-agent-core 消息。"""
        messages: list[Message] = []
        for item in (conversation_history or [])[-max_history_messages:]:
            role = item.get("role")
            content = item.get("content", "")
            if role == "user":
                messages.append(UserMessage(content=[TextContent(text=content)]))
            elif role == "assistant":
                messages.append(AssistantMessage(content=[TextContent(text=content)]))
        return messages

    async def _llm_context_for_turn(
        self,
        *,
        pi_context: AgentContext,
        messages: list[Message],
        config: AgentLoopConfig,
    ) -> AgentContext:
        """把当前 ReAct 消息链转换成供应商请求上下文。"""
        convert_result = config.convert_to_llm(messages)
        if inspect.isawaitable(convert_result):
            llm_messages = await convert_result
        else:
            llm_messages = convert_result
        return AgentContext(
            system_prompt=pi_context.system_prompt,
            messages=list(llm_messages),
            tools=pi_context.tools,
        )

    async def _stream_assistant_turn(
        self,
        *,
        agent: AgentDefinition,
        run_id: str,
        llm_context: AgentContext,
        config: AgentLoopConfig,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        state: dict[str, Any],
    ) -> tuple[AssistantMessage, list[str]]:
        """流式拉取单轮 assistant 响应并先缓冲文本增量。"""
        del agent, run_id, event_queue, event_callback
        response = self.stream_fn(
            config.model,
            llm_context,
            SimpleStreamOptions(
                api_key=config.api_key,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                reasoning=config.reasoning,
                session_id=config.session_id,
                transport=config.transport,
                thinking_budgets=config.thinking_budgets,
                max_retry_delay_ms=config.max_retry_delay_ms,
            ),
        )
        if inspect.isawaitable(response):
            response = await response
        if not isinstance(response, dict) or "events" not in response or "result" not in response:
            raise TypeError("StreamFn must return {'events': AsyncIterator, 'result': async callable}")

        text_deltas: list[str] = []
        async for raw_event in response["events"]:
            delta = self._text_delta_from_event(raw_event)
            if delta:
                if state["first_token_latency_ms"] is None:
                    state["first_token_latency_ms"] = round(
                        (perf_counter() - state["started_at"]) * 1000,
                        2,
                    )
                text_deltas.append(delta)

        result = response["result"]()
        if inspect.isawaitable(result):
            result = await result
        if not isinstance(result, AssistantMessage):
            raise TypeError("StreamFn result must be an AssistantMessage")
        assistant_message = _ReActStreamFn._single_tool_message(result)
        state["last_assistant_text"] = self.event_publisher.assistant_text(
            assistant_message
        )
        state["usage"] = self._usage_to_dict(getattr(assistant_message, "usage", None))
        return assistant_message, text_deltas

    @staticmethod
    def _assistant_tool_calls(message: AssistantMessage) -> list[ToolCall]:
        """从 assistant 消息中提取本轮工具调用。"""
        return [block for block in message.content if isinstance(block, ToolCall)]

    @staticmethod
    def _text_delta_from_event(raw_event: Any) -> str:
        """从底层流式事件中提取纯文本增量。"""
        if str(getattr(raw_event, "type", "") or "") != "text_delta":
            return ""
        return str(getattr(raw_event, "delta", "") or "")

    async def _publish_text_deltas(
        self,
        *,
        agent: AgentDefinition,
        run_id: str,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        state: dict[str, Any],
        text_deltas: list[str],
    ) -> None:
        """把已确认可见的 assistant 文本增量发布给前端。"""
        for content in text_deltas:
            if not content:
                continue
            state["chunk_index"] += 1
            state["response_parts"].append(content)
            self.trace_recorder.chunk(
                "agent.trace.intermediate.chunk",
                run_id=run_id,
                agent_name=agent.prompt_spec.name,
                chunk_index=state["chunk_index"],
                content_preview=DefaultTraceRecorder.preview_text(content),
                content_chars=len(content),
            )
            await self.event_publisher.publish(
                event_queue=event_queue,
                event_callback=event_callback,
                event=self.event_publisher.text_delta(content),
            )

    async def _execute_react_tool(
        self,
        *,
        agent: AgentDefinition,
        run_id: str,
        tool_call: ToolCall,
        context: dict[str, Any],
        confirmation_queue: asyncio.Queue | None,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        state: dict[str, Any],
        executed_tools: list[dict[str, Any]],
    ) -> ToolResultMessage:
        """执行一个 ReAct 工具调用并返回可追加到消息链的 tool result。"""
        state["tool_call_count"] += 1
        self.trace_recorder.tool_call_detected(
            agent,
            run_id,
            ToolExecutionStartEvent(
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
                args=tool_call.arguments,
            ),
            state,
        )
        result = await self.tool_pipeline.execute_tool_result(
            agent=agent,
            run_id=run_id,
            call_id=tool_call.id,
            tool_name=tool_call.name,
            tool_input=tool_call.arguments,
            context=context,
            confirmation_queue=confirmation_queue,
            event_queue=event_queue,
            event_callback=event_callback,
            executed_tools=executed_tools,
            stream_state=state,
        )
        return ToolResultMessage(
            tool_call_id=tool_call.id,
            tool_name=tool_call.name,
            content=result.content,
            details=result.details,
            is_error=False,
        )

    @staticmethod
    def _usage_to_dict(usage: Any) -> dict[str, Any]:
        """用于把 pi-agent-core usage 转换成日志友好的字典。"""
        if usage is None:
            return {}
        return {
            "input": int(getattr(usage, "input", 0) or 0),
            "output": int(getattr(usage, "output", 0) or 0),
            "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
            "cache_read": int(getattr(usage, "cache_read", 0) or 0),
            "cache_write": int(getattr(usage, "cache_write", 0) or 0),
        }


__all__ = ["ReActTurnRunner"]
