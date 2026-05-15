"""用于提供基于 pi-agent-core 的业务 Agent 运行时。"""

from __future__ import annotations

import asyncio
import inspect
import json
from copy import deepcopy
from itertools import count
from time import perf_counter
from typing import Any, AsyncGenerator
from uuid import uuid4

from pi_agent_core import (
    AgentContext,
    AgentLoopConfig,
    AgentTool,
    AgentToolResult,
    AgentToolSchema,
    AssistantMessage,
    SimpleStreamOptions,
    TextContent,
    ToolCall,
    ToolExecutionStartEvent,
    ToolResultMessage,
    UserMessage,
)
from pi_agent_core.types import Message, StreamFn

from app.infra.config import settings
from app.runtime.contracts import AgentDefinition, RuntimeEventCallback
from app.runtime.message_conversion import convert_resume_messages_to_llm
from app.runtime.openrouter_adapter import (
    build_openrouter_loop_config,
    openrouter_chat_model_name,
)
from app.runtime.trace_recorder import DefaultTraceRecorder
from app.runtime.tool_confirmation import (
    ToolConfirmationPolicy,
)
from app.runtime.runtime_event_adapter import (
    RuntimeEventPublisher,
)
from app.runtime.pi_agent_openrouter import stream_openrouter
from app.types.stream import ResumeStreamEvent

_SENTINEL = object()


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


class PiAgentRuntime:
    """Runtime adapter that uses pi-agent-core as the execution loop."""

    def __init__(
        self,
        stream_fn: StreamFn | None = None,
        confirmation_policy: ToolConfirmationPolicy | None = None,
    ):
        """用于初始化当前对象。"""
        self.stream_fn = _ReActStreamFn(stream_fn or stream_openrouter)
        self.confirmation_policy = confirmation_policy or ToolConfirmationPolicy()
        self.trace_recorder = DefaultTraceRecorder()
        self.event_publisher = RuntimeEventPublisher()

    async def run(
        self,
        agent: AgentDefinition,
        user_message: str,
        context: dict[str, Any],
        conversation_history: list[dict[str, str]] | None = None,
        event_callback: RuntimeEventCallback | None = None,
    ) -> dict[str, Any]:
        """用于处理run。"""
        run_id = uuid4().hex
        executed_tools: list[dict[str, Any]] = []
        state = self._new_stream_state()
        pi_context, prompts, config = self._build_loop_inputs(
            agent=agent,
            user_message=user_message,
            context=context,
            conversation_history=conversation_history,
            run_id=run_id,
            confirmation_queue=None,
            event_queue=None,
            event_callback=event_callback,
            executed_tools=executed_tools,
            stream_state=state,
        )
        self.trace_recorder.run_started(
            agent,
            run_id,
            "sync",
            user_message,
            conversation_history,
        )
        self.trace_recorder.prompt_rendered(agent, run_id, pi_context.system_prompt)
        self.event_publisher.emit(
            event_callback,
            self.event_publisher.prompt_rendered(
                agent,
                pi_context.system_prompt,
                user_message,
            ),
        )
        await self._run_react_loop(
            agent=agent,
            run_id=run_id,
            pi_context=pi_context,
            prompts=prompts,
            config=config,
            context=context,
            confirmation_queue=None,
            event_queue=None,
            event_callback=event_callback,
            state=state,
            executed_tools=executed_tools,
        )
        response_event = self._llm_response_event(agent, state)
        self.trace_recorder.llm_response(agent, run_id, response_event)
        self.event_publisher.emit(event_callback, response_event)
        self.trace_recorder.run_completed(agent, run_id, "sync", state)
        return {"content": "".join(state["response_parts"]), "tool_calls": executed_tools}

    async def run_stream(
        self,
        agent: AgentDefinition,
        user_message: str,
        context: dict[str, Any],
        conversation_history: list[dict[str, str]] | None = None,
        confirmation_queue: asyncio.Queue | None = None,
        event_callback: RuntimeEventCallback | None = None,
    ) -> AsyncGenerator[ResumeStreamEvent, None]:
        """用于拉取模型流并写入本地事件队列。"""
        run_id = uuid4().hex
        executed_tools: list[dict[str, Any]] = []
        event_queue: asyncio.Queue[Any] = asyncio.Queue()
        state = self._new_stream_state()
        pi_context, prompts, config = self._build_loop_inputs(
            agent=agent,
            user_message=user_message,
            context=context,
            conversation_history=conversation_history,
            run_id=run_id,
            confirmation_queue=confirmation_queue,
            event_queue=event_queue,
            event_callback=event_callback,
            executed_tools=executed_tools,
            stream_state=state,
        )
        self.trace_recorder.run_started(
            agent,
            run_id,
            "stream",
            user_message,
            conversation_history,
        )
        self.trace_recorder.prompt_rendered(agent, run_id, pi_context.system_prompt)
        prompt_event = self.event_publisher.prompt_rendered(
            agent,
            pi_context.system_prompt,
            user_message,
        )
        self.event_publisher.emit(event_callback, prompt_event)
        yield prompt_event

        producer = asyncio.create_task(
            self._produce_stream_events(
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
        )
        while True:
            event = await event_queue.get()
            if event is _SENTINEL:
                break
            yield event
        await producer
        self.trace_recorder.run_completed(agent, run_id, "stream", state)

    async def _produce_stream_events(
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
    ) -> None:
        """用于处理produce流式events。"""
        try:
            await self._run_react_loop(
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
            response_event = self._llm_response_event(agent, state)
            self.trace_recorder.llm_response(agent, run_id, response_event)
            await self.event_publisher.publish(
                event_queue=event_queue,
                event_callback=event_callback,
                event=response_event,
            )
            await event_queue.put(_SENTINEL)

    async def _run_react_loop(
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
            request_event = self._llm_request_event(agent, llm_context, [], state)
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

    def _assistant_tool_calls(self, message: AssistantMessage) -> list[ToolCall]:
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
        result = await self._execute_tool_result(
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

    def _build_loop_inputs(
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
        """用于构建循环输入。"""
        context["conversation_history"] = conversation_history or []
        context["confirmed_diff_items"] = stream_state["confirmed_diff_items"]
        tool_profile = self._tool_profile(agent, context)
        context["tool_profile"] = tool_profile
        tools_schema = self._profiled_tool_schemas(agent, tool_profile)
        context["available_tool_names"] = self._tool_names_from_schemas(tools_schema)
        prompt_context = agent.prompt_context_builder(context)
        system_prompt = agent.prompt_spec.render(**prompt_context)
        tools = self._build_tools(
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
            messages=self._history_messages(
                conversation_history,
                agent.max_history_messages,
            ),
            tools=tools,
        )
        stream_state["tool_profile"] = tool_profile
        stream_state["tool_names"] = self._tool_names_from_schemas(tools_schema)
        stream_state["prompt_chars"] = len(system_prompt)
        prompts: list[Message] = [UserMessage(content=[TextContent(text=user_message)])]
        config = build_openrouter_loop_config(
            agent,
            convert_to_llm=convert_resume_messages_to_llm,
        )
        return pi_context, prompts, config

    def _build_tools(
        self,
        *,
        agent: AgentDefinition,
        tools_schema: list[dict[str, Any]],
        context: dict[str, Any],
        confirmation_queue: asyncio.Queue | None,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        run_id: str,
        executed_tools: list[dict[str, Any]],
        stream_state: dict[str, Any],
    ) -> list[AgentTool]:
        """用于构建工具列表。"""
        tools: list[AgentTool] = []
        lock = asyncio.Lock()
        for schema in tools_schema:
            function = schema.get("function", {})
            tool_name = function.get("name")
            if not isinstance(tool_name, str) or not tool_name:
                continue
            tools.append(
                self._build_tool(
                    agent=agent,
                    tool_name=tool_name,
                    function=function,
                    context=context,
                    confirmation_queue=confirmation_queue,
                    event_queue=event_queue,
                    event_callback=event_callback,
                    run_id=run_id,
                    executed_tools=executed_tools,
                    lock=lock,
                    stream_state=stream_state,
                )
            )
        return tools

    def _build_tool(
        self,
        *,
        agent: AgentDefinition,
        tool_name: str,
        function: dict[str, Any],
        context: dict[str, Any],
        confirmation_queue: asyncio.Queue | None,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        run_id: str,
        executed_tools: list[dict[str, Any]],
        lock: asyncio.Lock,
        stream_state: dict[str, Any],
    ) -> AgentTool:
        """用于构建工具。"""

        async def execute(
            tool_call_id: str,
            params: dict[str, Any],
            *_args: Any,
        ) -> AgentToolResult:
            """用于执行一次业务工具调用。"""
            if tool_name in agent.auto_execute_tool_names:
                return await self._execute_tool_result(
                    agent=agent,
                    run_id=run_id,
                    call_id=tool_call_id,
                    tool_name=tool_name,
                    tool_input=params,
                    context=context,
                    confirmation_queue=confirmation_queue,
                    event_queue=event_queue,
                    event_callback=event_callback,
                    executed_tools=executed_tools,
                    stream_state=stream_state,
                )
            async with lock:
                return await self._execute_tool_result(
                    agent=agent,
                    run_id=run_id,
                    call_id=tool_call_id,
                    tool_name=tool_name,
                    tool_input=params,
                    context=context,
                    confirmation_queue=confirmation_queue,
                    event_queue=event_queue,
                    event_callback=event_callback,
                    executed_tools=executed_tools,
                    stream_state=stream_state,
                )

        return AgentTool(
            name=tool_name,
            description=str(function.get("description", "")),
            parameters=self._tool_schema(function.get("parameters")),
            execute=execute,
        )

    async def _execute_tool_result(
        self,
        *,
        agent: AgentDefinition,
        run_id: str,
        call_id: str,
        tool_name: str,
        tool_input: dict[str, Any],
        context: dict[str, Any],
        confirmation_queue: asyncio.Queue | None,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        executed_tools: list[dict[str, Any]],
        stream_state: dict[str, Any],
    ) -> AgentToolResult:
        """用于处理执行工具结果。"""
        output = await self._execute_tool(
            agent=agent,
            run_id=run_id,
            call_id=call_id,
            tool_name=tool_name,
            tool_input=tool_input,
            context=context,
            confirmation_queue=confirmation_queue,
            event_queue=event_queue,
            event_callback=event_callback,
            executed_tools=executed_tools,
            stream_state=stream_state,
        )
        return AgentToolResult(content=[TextContent(text=output)], details=output)

    async def _execute_tool(
        self,
        *,
        agent: AgentDefinition,
        run_id: str,
        call_id: str,
        tool_name: str,
        tool_input: dict[str, Any],
        context: dict[str, Any],
        confirmation_queue: asyncio.Queue | None,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        executed_tools: list[dict[str, Any]],
        stream_state: dict[str, Any],
    ) -> str:
        """用于处理执行工具。"""
        tool_started_at = perf_counter()
        confirmation_decision = self.confirmation_policy.before_tool_call(
            confirmation_queue=confirmation_queue,
            tool_name=tool_name,
            auto_execute_tool_names=agent.auto_execute_tool_names,
        )
        needs_confirmation = confirmation_decision.requires_confirmation
        tool_call = self._tool_call_payload(call_id, tool_name, tool_input)
        await self._publish_visible_tool_call(
            call_id=call_id,
            tool_name=tool_name,
            tool_input=tool_input,
            event_queue=event_queue,
            event_callback=event_callback,
        )
        self.trace_recorder.tool_requested(
            agent,
            run_id,
            call_id,
            tool_name,
            tool_input,
            needs_confirmation,
        )
        preview = await self._maybe_confirm_tool(
            agent=agent,
            run_id=run_id,
            call_id=call_id,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_call=tool_call,
            context=context,
            confirmation_queue=confirmation_queue,
            event_queue=event_queue,
            event_callback=event_callback,
            executed_tools=executed_tools,
            needs_confirmation=needs_confirmation,
            tool_started_at=tool_started_at,
            stream_state=stream_state,
        )
        if isinstance(preview, str):
            return preview
        return await self._run_confirmed_tool(
            agent=agent,
            run_id=run_id,
            call_id=call_id,
            tool_name=tool_name,
            tool_call=tool_call,
            context=context,
            event_queue=event_queue,
            event_callback=event_callback,
            executed_tools=executed_tools,
            needs_confirmation=needs_confirmation,
            tool_started_at=tool_started_at,
            stream_state=stream_state,
        )

    async def _maybe_confirm_tool(
        self,
        *,
        agent: AgentDefinition,
        run_id: str,
        call_id: str,
        tool_name: str,
        tool_input: dict[str, Any],
        tool_call: dict[str, Any],
        context: dict[str, Any],
        confirmation_queue: asyncio.Queue | None,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        executed_tools: list[dict[str, Any]],
        needs_confirmation: bool,
        tool_started_at: float,
        stream_state: dict[str, Any],
    ) -> dict[str, Any] | str | None:
        """用于处理maybeconfirm工具。"""
        if not needs_confirmation:
            return None
        assert confirmation_queue is not None
        preview_context = {"resume_content": deepcopy(context.get("resume_content"))}
        preview_result = agent.tool_executor(tool_call, preview_context)
        diff_summary = preview_result.get("display_message") or "执行完成"
        result = preview_result.get("result", {})
        diff_items = result.get("diff_items", []) if isinstance(result, dict) else []
        self.trace_recorder.tool_preview(agent, run_id, call_id, tool_name, preview_result)
        await self.event_publisher.publish(
            event_queue=event_queue,
            event_callback=event_callback,
            event=self.event_publisher.tool_pending(
                call_id=call_id,
                tool_name=tool_name,
                tool_call=tool_call,
                tool_display_name=preview_result["tool_name"],
                tool_input=tool_input,
                diff_summary=diff_summary,
                diff_items=diff_items,
                tool_calls=executed_tools,
            ),
        )
        wait_started_at = perf_counter()
        confirmed = await self.confirmation_policy.wait_for_decision(confirmation_queue)
        confirmation_wait_ms = round((perf_counter() - wait_started_at) * 1000, 2)
        stream_state["confirmation_wait_ms"] += confirmation_wait_ms
        confirmation_result = self.confirmation_policy.after_tool_decision(
            confirmed=confirmed,
        )
        self.trace_recorder.tool_confirmation(
            agent,
            run_id,
            call_id,
            tool_name,
            preview_result["tool_name"],
            confirmed,
            confirmation_wait_ms,
            confirmation_result.terminate_turn,
        )
        if confirmed:
            return preview_result
        rejected = {"success": False, "error": "用户拒绝了此修改"}
        await self._publish_rejected_tool(
            agent=agent,
            run_id=run_id,
            call_id=call_id,
            tool_name=tool_name,
            tool_display_name=preview_result["tool_name"],
            diff_summary=diff_summary,
            diff_items=diff_items,
            result=rejected,
            event_queue=event_queue,
            event_callback=event_callback,
            executed_tools=executed_tools,
            tool_started_at=tool_started_at,
        )
        await self._publish_terminal_text(
            agent=agent,
            run_id=run_id,
            stream_state=stream_state,
            event_queue=event_queue,
            event_callback=event_callback,
            content="已取消这处修改。",
        )
        return json.dumps(rejected, ensure_ascii=False)

    async def _run_confirmed_tool(
        self,
        *,
        agent: AgentDefinition,
        run_id: str,
        call_id: str,
        tool_name: str,
        tool_call: dict[str, Any],
        context: dict[str, Any],
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        executed_tools: list[dict[str, Any]],
        needs_confirmation: bool,
        tool_started_at: float,
        stream_state: dict[str, Any],
    ) -> str:
        """用于处理run已确认工具。"""
        tool_result = agent.tool_executor(tool_call, context)
        result = tool_result.get("result", {})
        if needs_confirmation:
            self._remember_confirmed_diff_items(stream_state, result)
        display_message = tool_result.get("display_message")
        self.trace_recorder.tool_executed(
            agent,
            run_id,
            call_id,
            tool_name,
            tool_result,
            tool_started_at,
        )
        executed_tools.append(self._executed_tool_summary(tool_result, result))
        await self._publish_tool_result(
            call_id=call_id,
            tool_name=tool_name,
            tool_result=tool_result,
            result=result,
            display_message=display_message,
            event_queue=event_queue,
            event_callback=event_callback,
            executed_tools=executed_tools,
            context=context,
            needs_confirmation=needs_confirmation,
        )
        return json.dumps(result, ensure_ascii=False)

    async def _publish_terminal_text(
        self,
        *,
        agent: AgentDefinition,
        run_id: str,
        stream_state: dict[str, Any],
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        content: str,
    ) -> None:
        """用于在确认后用确定性文本结束当前轮次，避免再次调用模型。"""
        stream_state["chunk_index"] += 1
        stream_state["response_parts"].append(content)
        self.trace_recorder.chunk(
            "agent.trace.intermediate.chunk",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            chunk_index=stream_state["chunk_index"],
            content_preview=DefaultTraceRecorder.preview_text(content),
            content_chars=len(content),
        )
        await self.event_publisher.publish(
            event_queue=event_queue,
            event_callback=event_callback,
            event=self.event_publisher.text_delta(content),
        )

    async def _publish_visible_tool_call(
        self,
        *,
        call_id: str,
        tool_name: str,
        tool_input: dict[str, Any],
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
    ) -> None:
        """用于发布visible工具调用。"""
        tool_call = self._tool_call_payload(call_id, tool_name, tool_input)
        await self.event_publisher.publish(
            event_queue=event_queue,
            event_callback=event_callback,
            event=self.event_publisher.tool_call_started(
                call_id=call_id,
                tool_name=tool_name,
                tool_call=tool_call,
                tool_input=tool_call["function"]["arguments"],
            ),
        )

    async def _publish_tool_result(
        self,
        *,
        call_id: str,
        tool_name: str,
        tool_result: dict[str, Any],
        result: Any,
        display_message: str | None,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        executed_tools: list[dict[str, Any]],
        context: dict[str, Any],
        needs_confirmation: bool,
    ) -> None:
        """用于发布工具结果。"""
        if self._is_tool_failure(tool_result):
            event = self.event_publisher.tool_call_failed(
                call_id=call_id,
                tool_name=tool_name,
                tool_display_name=tool_result["tool_name"],
                tool_calls=executed_tools,
                result=result,
                display_message=display_message,
            )
        elif needs_confirmation:
            event = self.event_publisher.tool_confirmed(
                call_id=call_id,
                tool_name=tool_name,
                tool_display_name=tool_result["tool_name"],
                tool_calls=executed_tools,
                qr_images=[tool_result["qr_image"]] if tool_result.get("qr_image") else [],
                result=result,
                display_message=display_message,
                diff_summary=result.get("diff_summary") if isinstance(result, dict) else None,
                diff_items=result.get("diff_items", []) if isinstance(result, dict) else [],
                context=context,
            )
        else:
            event = self.event_publisher.tool_result(
                call_id=call_id,
                tool_name=tool_name,
                tool_display_name=tool_result["tool_name"],
                tool_calls=executed_tools,
                result=result,
                display_message=display_message,
                context=context,
            )
        await self.event_publisher.publish(
            event_queue=event_queue,
            event_callback=event_callback,
            event=event,
        )

    async def _publish_rejected_tool(
        self,
        *,
        agent: AgentDefinition,
        run_id: str,
        call_id: str,
        tool_name: str,
        tool_display_name: str,
        diff_summary: str,
        diff_items: Any,
        result: dict[str, Any],
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        executed_tools: list[dict[str, Any]],
        tool_started_at: float,
    ) -> None:
        """用于发布rejected工具。"""
        self.trace_recorder.tool_rejected(
            agent,
            run_id,
            call_id,
            tool_name,
            tool_display_name,
            tool_started_at,
        )
        await self.event_publisher.publish(
            event_queue=event_queue,
            event_callback=event_callback,
            event=self.event_publisher.tool_rejected(
                call_id=call_id,
                tool_name=tool_name,
                tool_display_name=tool_display_name,
                diff_summary=diff_summary,
                diff_items=diff_items,
                result=result,
                tool_calls=executed_tools,
            ),
        )

    @staticmethod
    def _tool_schema(value: Any) -> AgentToolSchema:
        """用于处理工具结构。"""
        if not isinstance(value, dict):
            return AgentToolSchema()
        properties = value.get("properties")
        required = value.get("required")
        return AgentToolSchema(
            type=str(value.get("type") or "object"),
            properties=properties if isinstance(properties, dict) else {},
            required=required if isinstance(required, list) else [],
        )

    @staticmethod
    def _history_messages(
        conversation_history: list[dict[str, str]] | None,
        max_history_messages: int,
    ) -> list[Message]:
        """用于处理历史消息列表。"""
        messages: list[Message] = []
        for item in (conversation_history or [])[-max_history_messages:]:
            role = item.get("role")
            content = item.get("content", "")
            if role == "user":
                messages.append(UserMessage(content=[TextContent(text=content)]))
            elif role == "assistant":
                messages.append(AssistantMessage(content=[TextContent(text=content)]))
        return messages

    @staticmethod
    def _tool_call_payload(
        call_id: str,
        tool_name: str,
        tool_input: dict[str, Any],
    ) -> dict[str, Any]:
        """用于处理工具调用载荷。"""
        return {
            "id": call_id,
            "type": "function",
            "function": {"name": tool_name, "arguments": tool_input},
        }

    @staticmethod
    def _new_stream_state() -> dict[str, Any]:
        """用于处理new流式state。"""
        return RuntimeEventPublisher.new_stream_state()

    def _llm_request_event(
        self,
        agent: AgentDefinition,
        context: AgentContext,
        prompts: list[Message],
        state: dict[str, Any],
    ) -> ResumeStreamEvent:
        """用于处理模型请求事件。"""
        return self.event_publisher.llm_request(agent, context, prompts, state)

    def _llm_response_event(
        self,
        agent: AgentDefinition,
        state: dict[str, Any],
    ) -> ResumeStreamEvent:
        """用于处理模型响应事件。"""
        return self.event_publisher.llm_response(agent, state)

    @staticmethod
    def _executed_tool_summary(
        tool_result: dict[str, Any],
        result: Any,
    ) -> dict[str, Any]:
        """用于处理executed工具summary。"""
        return {
            "name": tool_result["tool_name"],
            "result": result.get("diff_summary") if isinstance(result, dict) else tool_result.get("display_message"),
            "success": result.get("success") if isinstance(result, dict) else None,
        }

    @staticmethod
    def _remember_confirmed_diff_items(
        stream_state: dict[str, Any],
        result: Any,
    ) -> None:
        """用于把已确认工具产生的 diff 提供给后续只读摘要工具。"""
        if not isinstance(result, dict) or result.get("success") is False:
            return
        diff_items = result.get("diff_items")
        if not isinstance(diff_items, list):
            return
        confirmed = stream_state.get("confirmed_diff_items")
        if isinstance(confirmed, list):
            confirmed.extend(item for item in diff_items if isinstance(item, dict))

    @staticmethod
    def _is_tool_failure(tool_result: dict[str, Any]) -> bool:
        """用于判断工具failure。"""
        result = tool_result.get("result")
        return isinstance(result, dict) and result.get("success") is False

    @staticmethod
    def _tool_names(agent: AgentDefinition) -> list[str]:
        """用于处理工具名称。"""
        names: list[str] = []
        for schema in agent.tools_schema:
            name = schema.get("function", {}).get("name")
            if isinstance(name, str) and name:
                names.append(name)
        return names

    @staticmethod
    def _optional_tool_names(agent: AgentDefinition) -> list[str | None]:
        """用于处理可选工具名称。"""
        return list(PiAgentRuntime._tool_names(agent))

    @staticmethod
    def _chat_model_name() -> str:
        """用于处理聊天模型name。"""
        return openrouter_chat_model_name()

    @staticmethod
    def _tool_profile(agent: AgentDefinition, context: dict[str, Any]) -> str:
        """用于选择当前轮次实际使用的工具 profile。"""
        requested = context.get("tool_profile")
        if isinstance(requested, str) and requested in agent.tool_profiles:
            return requested
        return agent.default_tool_profile

    @staticmethod
    def _profiled_tool_schemas(
        agent: AgentDefinition,
        tool_profile: str,
    ) -> list[dict[str, Any]]:
        """用于按工具 profile 过滤暴露给模型的工具 schema。"""
        allowed = agent.tool_profiles.get(tool_profile)
        if allowed is None:
            allowed = agent.tool_profiles.get(agent.default_tool_profile)
        if not allowed:
            return []
        return [
            schema
            for schema in agent.tools_schema
            if schema.get("function", {}).get("name") in allowed
        ]

    @staticmethod
    def _tool_names_from_schemas(schemas: list[dict[str, Any]]) -> list[str]:
        """用于从工具 schema 列表读取工具名。"""
        names: list[str] = []
        for schema in schemas:
            name = schema.get("function", {}).get("name")
            if isinstance(name, str) and name:
                names.append(name)
        return names

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


__all__ = ["PiAgentRuntime"]
