"""用于提供基于 pi-agent-core 的业务 Agent 运行时。"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import logging
from time import perf_counter
from typing import Any, AsyncGenerator
from uuid import uuid4

from pi_agent_core import (
    AgentContext,
    AgentLoopConfig,
    AgentToolSchema,
    AssistantMessage,
    ToolCall,
    ToolExecutionStartEvent,
)
from pi_agent_core.types import Message, StreamFn

from app.agents.resume.stream_events import (
    llm_response_event,
    prompt_rendered_event,
)
from app.agents.resume.agent_loop import ResumeAgentLoop
from app.agents.resume.tool_execution import ResumeToolExecutionStage
from app.agents.resume.turn_context import ResumeTurnContextBuilder
from app.infra.config import settings
from app.runtime.contracts import AgentDefinition, RuntimeEventCallback
from app.runtime.openrouter_adapter import (
    openrouter_chat_model_name,
)
from app.runtime.tool_confirmation import (
    ToolConfirmationPolicy,
)
from app.runtime.runtime_event_adapter import (
    emit_runtime_event,
    publish_runtime_event,
)
from app.runtime.pi_agent_openrouter import stream_openrouter
from app.types.stream import ResumeStreamEvent

logger = logging.getLogger(__name__)

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
        self.tool_stage = ResumeToolExecutionStage(
            confirmation_policy=confirmation_policy or ToolConfirmationPolicy()
        )
        self.agent_loop = ResumeAgentLoop(
            stream_fn=self.stream_fn,
            tool_stage=self.tool_stage,
        )
        self.turn_context_builder = ResumeTurnContextBuilder(
            tool_stage=self.tool_stage,
        )

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
        error_type: str | None = None
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
        self._trace_run_start(agent, run_id, "sync", user_message, conversation_history)
        self._trace_prompt(agent, run_id, pi_context.system_prompt)
        self._emit_event(
            event_callback,
            self._prompt_rendered_event(agent, pi_context.system_prompt, user_message),
        )
        try:
            await self.agent_loop.run(
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
                model_name=self._chat_model_name(),
            )
            response_event = self._llm_response_event(agent, state)
            self._trace_llm_response(agent, run_id, response_event)
            self._emit_event(event_callback, response_event)
            self._trace_run_completed(agent, run_id, "sync", state)
            return {"content": "".join(state["response_parts"]), "tool_calls": executed_tools}
        except Exception as exc:
            error_type = type(exc).__name__
            raise
        finally:
            self._log_run_summary(
                agent=agent,
                run_id=run_id,
                mode="sync",
                state=state,
                success=error_type is None,
                error_type=error_type,
            )

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
        self._trace_run_start(agent, run_id, "stream", user_message, conversation_history)
        self._trace_prompt(agent, run_id, pi_context.system_prompt)
        prompt_event = self._prompt_rendered_event(
            agent,
            pi_context.system_prompt,
            user_message,
        )
        self._emit_event(event_callback, prompt_event)
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
        try:
            while True:
                event = await event_queue.get()
                if event is _SENTINEL:
                    break
                yield event
            await producer
        finally:
            if not producer.done():
                producer.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await producer
        self._trace_run_completed(agent, run_id, "stream", state)

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
            await self.agent_loop.run(
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
                model_name=self._chat_model_name(),
            )
        except Exception as exc:
            state["error_type"] = type(exc).__name__
            raise
        finally:
            response_event = self._llm_response_event(agent, state)
            self._trace_llm_response(agent, run_id, response_event)
            await self._publish_event(
                event_queue=event_queue,
                event_callback=event_callback,
                event=response_event,
            )
            error_type = state.get("error_type")
            self._log_run_summary(
                agent=agent,
                run_id=run_id,
                mode="stream",
                state=state,
                success=not isinstance(error_type, str),
                error_type=error_type if isinstance(error_type, str) else None,
            )
            await event_queue.put(_SENTINEL)

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
        """用于兼容旧测试入口，并委托 turn context builder。"""
        return self.turn_context_builder.build_loop_inputs(
            agent=agent,
            user_message=user_message,
            context=context,
            conversation_history=conversation_history,
            run_id=run_id,
            confirmation_queue=confirmation_queue,
            event_queue=event_queue,
            event_callback=event_callback,
            executed_tools=executed_tools,
            stream_state=stream_state,
        )

    @staticmethod
    def _tool_schema(value: Any) -> AgentToolSchema:
        """用于兼容旧测试入口，并委托 turn context builder。"""
        return ResumeTurnContextBuilder.tool_schema(value)

    @staticmethod
    def _history_messages(
        conversation_history: list[dict[str, str]] | None,
        max_history_messages: int,
    ) -> list[Message]:
        """用于兼容旧测试入口，并委托 turn context builder。"""
        return ResumeTurnContextBuilder.history_messages(
            conversation_history,
            max_history_messages,
        )

    @staticmethod
    def _new_stream_state() -> dict[str, Any]:
        """用于处理new流式state。"""
        return {
            "started_at": perf_counter(),
            "chunk_index": 0,
            "response_parts": [],
            "last_assistant_text": "",
            "confirmed_diff_items": [],
            "tool_profile": "",
            "tool_names": [],
            "visible_tool_call_ids": set(),
            "unexpected_tool_call_names": set(),
            "prompt_chars": 0,
            "tool_call_count": 0,
            "first_token_latency_ms": None,
            "usage": {},
            "confirmation_wait_ms": 0.0,
            "mutation_claim_retry_count": 0,
        }

    def _llm_request_event(
        self,
        agent: AgentDefinition,
        context: AgentContext,
        prompts: list[Message],
        state: dict[str, Any],
    ) -> ResumeStreamEvent:
        """用于兼容旧测试入口，并委托 agent loop 生成请求事件。"""
        return self.agent_loop.llm_request_event(
            agent,
            context,
            prompts,
            state,
            self._chat_model_name(),
        )

    def _llm_response_event(
        self,
        agent: AgentDefinition,
        state: dict[str, Any],
    ) -> ResumeStreamEvent:
        """用于处理模型响应事件。"""
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
    def _prompt_rendered_event(
        agent: AgentDefinition,
        system_prompt: str,
        user_message: str,
    ) -> ResumeStreamEvent:
        """用于处理提示词渲染结果事件。"""
        return prompt_rendered_event(
            agent_name=agent.prompt_spec.name,
            system_prompt=system_prompt,
            user_message_preview=str(user_message)[:1500],
        )

    @staticmethod
    def _message_to_dict(message: Message) -> dict[str, Any]:
        """用于兼容旧测试入口，并委托 agent loop 转换消息。"""
        return ResumeAgentLoop.message_to_dict(message)

    @staticmethod
    def _assistant_text(message: Any) -> str:
        """用于兼容旧测试入口，并委托 agent loop 提取文本。"""
        return ResumeAgentLoop.assistant_text(message)

    def _trace_run_start(
        self,
        agent: AgentDefinition,
        run_id: str,
        mode: str,
        user_message: str,
        conversation_history: list[dict[str, str]] | None,
    ) -> None:
        """用于处理追踪run开始。"""
        self._trace(
            "agent.trace.run.started",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            mode=mode,
            user_message_preview=self._preview_text(user_message),
            history_count=len(conversation_history or []),
            tool_names=list(agent.tool_profiles.get(agent.default_tool_profile, set())),
        )

    def _trace_prompt(
        self,
        agent: AgentDefinition,
        run_id: str,
        system_prompt: str,
    ) -> None:
        """用于处理追踪提示词。"""
        self._trace(
            "agent.trace.prompt.rendered",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            prompt_chars=len(system_prompt),
        )

    def _trace_llm_request(
        self,
        agent: AgentDefinition,
        run_id: str,
        event: ResumeStreamEvent,
    ) -> None:
        """用于兼容旧测试入口，并委托 agent loop 记录请求 trace。"""
        self.agent_loop.trace_llm_request(
            agent,
            run_id,
            event,
            self._chat_model_name(),
        )

    def _trace_llm_response(
        self,
        agent: AgentDefinition,
        run_id: str,
        event: ResumeStreamEvent,
    ) -> None:
        """用于处理追踪模型响应。"""
        self._trace(
            "agent.trace.llm.response",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            model=self._chat_model_name(),
            response_preview=self._preview_text(event.get("response_content")),
            response_chars=len(str(event.get("response_content") or "")),
            latency_ms=event.get("latency_ms"),
            first_token_latency_ms=event.get("first_token_latency_ms"),
            usage=event.get("usage"),
            confirmation_wait_ms=event.get("confirmation_wait_ms"),
        )

    def _trace_run_completed(
        self,
        agent: AgentDefinition,
        run_id: str,
        mode: str,
        state: dict[str, Any],
    ) -> None:
        """用于处理追踪runcompleted。"""
        self._trace(
            "agent.trace.run.completed",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            mode=mode,
            latency_ms=round((perf_counter() - state["started_at"]) * 1000, 2),
        )

    def _log_run_summary(
        self,
        *,
        agent: AgentDefinition,
        run_id: str,
        mode: str,
        state: dict[str, Any],
        success: bool,
        error_type: str | None,
    ) -> None:
        """用于记录一次 Resume Agent run 的单条结构化摘要。"""
        logger.info(
            "resume_agent.run.summary",
            extra={
                "agent_trace": True,
                "agent_name": agent.prompt_spec.name,
                "run_id": run_id,
                "mode": mode,
                "model": self._chat_model_name(),
                "tool_call_count": int(state.get("tool_call_count") or 0),
                "confirmation_wait_ms": round(
                    float(state.get("confirmation_wait_ms") or 0.0),
                    2,
                ),
                "elapsed_ms": round((perf_counter() - state["started_at"]) * 1000, 2),
                "success": success,
                "error_type": error_type or "-",
            },
        )

    def _trace_tool_requested(
        self,
        agent: AgentDefinition,
        run_id: str,
        call_id: str,
        tool_name: str,
        tool_input: dict[str, Any],
        needs_confirmation: bool,
    ) -> None:
        """用于兼容旧测试入口，并委托工具执行阶段记录请求。"""
        self.tool_stage.trace_tool_requested(
            agent,
            run_id,
            call_id,
            tool_name,
            tool_input,
            needs_confirmation,
        )

    def _trace_tool_preview(
        self,
        agent: AgentDefinition,
        run_id: str,
        call_id: str,
        tool_name: str,
        preview_result: dict[str, Any],
    ) -> None:
        """用于兼容旧测试入口，并委托工具执行阶段记录预览。"""
        self.tool_stage.trace_tool_preview(
            agent,
            run_id,
            call_id,
            tool_name,
            preview_result,
        )

    def _trace_tool_confirmation(
        self,
        agent: AgentDefinition,
        run_id: str,
        call_id: str,
        tool_name: str,
        display_name: str,
        confirmed: bool,
        confirmation_wait_ms: float,
        terminate_turn: bool,
    ) -> None:
        """用于兼容旧测试入口，并委托工具执行阶段记录确认。"""
        self.tool_stage.trace_tool_confirmation(
            agent,
            run_id,
            call_id,
            tool_name,
            display_name,
            confirmed,
            confirmation_wait_ms,
            terminate_turn,
        )

    def _trace_tool_executed(
        self,
        agent: AgentDefinition,
        run_id: str,
        call_id: str,
        tool_name: str,
        tool_result: dict[str, Any],
        tool_started_at: float,
    ) -> None:
        """用于兼容旧测试入口，并委托工具执行阶段记录执行。"""
        self.tool_stage.trace_tool_executed(
            agent,
            run_id,
            call_id,
            tool_name,
            tool_result,
            tool_started_at,
        )

    def _trace_tool_call_detected(
        self,
        agent: AgentDefinition,
        run_id: str,
        event: ToolExecutionStartEvent,
        state: dict[str, Any],
    ) -> None:
        """用于兼容旧测试入口，并委托 agent loop 记录工具调用。"""
        self.agent_loop.trace_tool_call_detected(
            agent,
            run_id,
            event,
            state,
        )

    def _trace_unexpected_tool_call(
        self,
        agent: AgentDefinition,
        run_id: str,
        event: ToolExecutionStartEvent,
        state: dict[str, Any],
    ) -> None:
        """用于兼容旧测试入口，并委托 agent loop 记录异常工具调用。"""
        self.agent_loop.trace_unexpected_tool_call(
            agent,
            run_id,
            event,
            state,
        )

    @staticmethod
    async def _publish_event(
        *,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        event: ResumeStreamEvent,
    ) -> None:
        """用于发布事件。"""
        await publish_runtime_event(
            event_queue=event_queue,
            event_callback=event_callback,
            event=event,
        )

    @staticmethod
    def _emit_event(
        event_callback: RuntimeEventCallback | None,
        event: ResumeStreamEvent,
    ) -> None:
        """用于发送事件。"""
        emit_runtime_event(event_callback, event)

    @staticmethod
    def _preview_text(value: Any, limit: int = 240) -> str:
        """用于兼容旧测试入口，并委托工具执行阶段生成预览。"""
        return ResumeToolExecutionStage.preview_text(value, limit=limit)

    @staticmethod
    def _trace(message: str, **fields: Any) -> None:
        """用于处理追踪。"""
        if not settings.AGENT_TRACE_LOG_ENABLED:
            return
        level = int(fields.pop("log_level", logging.INFO))
        logger.log(level, message, extra={"agent_trace": True, **fields})

    @staticmethod
    def _trace_chunk(message: str, **fields: Any) -> None:
        """用于在需要排查流式细节时记录单个 chunk。"""
        if not settings.AGENT_TRACE_CHUNK_LOG_ENABLED:
            return
        PiAgentRuntime._trace(message, **fields)

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
        """用于兼容旧测试入口，并委托 turn context builder。"""
        return ResumeTurnContextBuilder.tool_profile(agent, context)

    @staticmethod
    def _profiled_tool_schemas(
        agent: AgentDefinition,
        tool_profile: str,
    ) -> list[dict[str, Any]]:
        """用于兼容旧测试入口，并委托 turn context builder。"""
        return ResumeTurnContextBuilder.profiled_tool_schemas(agent, tool_profile)

    @staticmethod
    def _tool_names_from_schemas(schemas: list[dict[str, Any]]) -> list[str]:
        """用于兼容旧测试入口，并委托 turn context builder。"""
        return ResumeTurnContextBuilder.tool_names_from_schemas(schemas)

    @staticmethod
    def _usage_to_dict(usage: Any) -> dict[str, Any]:
        """用于兼容旧测试入口，并委托 agent loop 转换 usage。"""
        return ResumeAgentLoop.usage_to_dict(usage)


__all__ = ["PiAgentRuntime"]
