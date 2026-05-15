"""用于提供基于 pi-agent-core 的业务 Agent 运行时。"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncGenerator
from uuid import uuid4

from pi_agent_core import (
    AgentContext,
    AgentLoopConfig,
)
from pi_agent_core.types import Message, StreamFn

from app.infra.config import settings
from app.runtime.contracts import AgentDefinition, RuntimeEventCallback
from app.runtime.react_turn_runner import ReActTurnRunner
from app.runtime.trace_recorder import DefaultTraceRecorder
from app.runtime.tool_confirmation import (
    ToolConfirmationPolicy,
)
from app.runtime.tool_execution_pipeline import ToolExecutionPipeline
from app.runtime.runtime_event_adapter import (
    RuntimeEventPublisher,
)
from app.runtime.pi_agent_openrouter import stream_openrouter
from app.types.stream import ResumeStreamEvent

_SENTINEL = object()


class PiAgentRuntime:
    """Runtime adapter that uses pi-agent-core as the execution loop."""

    def __init__(
        self,
        stream_fn: StreamFn | None = None,
        confirmation_policy: ToolConfirmationPolicy | None = None,
    ):
        """用于初始化当前对象。"""
        self.confirmation_policy = confirmation_policy or ToolConfirmationPolicy()
        self.trace_recorder = DefaultTraceRecorder()
        self.event_publisher = RuntimeEventPublisher()
        self.tool_pipeline = ToolExecutionPipeline(
            confirmation_policy=self.confirmation_policy,
            event_publisher=self.event_publisher,
            trace_recorder=self.trace_recorder,
        )
        self.turn_runner = ReActTurnRunner(
            stream_fn=stream_fn or stream_openrouter,
            tool_pipeline=self.tool_pipeline,
            event_publisher=self.event_publisher,
            trace_recorder=self.trace_recorder,
        )
        self.stream_fn = self.turn_runner.stream_fn

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
        await self.turn_runner.run_loop(
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
            self.turn_runner.produce_stream_events(
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
                done_sentinel=_SENTINEL,
            )
        )
        while True:
            event = await event_queue.get()
            if event is _SENTINEL:
                break
            yield event
        await producer
        self.trace_recorder.run_completed(agent, run_id, "stream", state)

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
        return self.turn_runner.build_loop_inputs(
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
    def _history_messages(
        conversation_history: list[dict[str, str]] | None,
        max_history_messages: int,
    ) -> list[Message]:
        """用于处理历史消息列表。"""
        return ReActTurnRunner.history_messages(conversation_history, max_history_messages)

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
    def _usage_to_dict(usage: Any) -> dict[str, Any]:
        """用于把 pi-agent-core usage 转换成日志友好的字典。"""
        if usage is None:
            return {}
        return ReActTurnRunner._usage_to_dict(usage)


__all__ = ["PiAgentRuntime"]
