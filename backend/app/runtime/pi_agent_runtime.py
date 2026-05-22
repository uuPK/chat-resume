"""用于提供基于 pi-agent-core 的业务 Agent 运行时。"""

from __future__ import annotations

import asyncio
import inspect
from typing import Any, AsyncGenerator

from pi_agent_core import (
    AgentContext,
    AgentLoopConfig,
    AgentToolSchema,
    AssistantMessage,
    ToolCall,
    ToolExecutionStartEvent,
)
from pi_agent_core.types import Message, StreamFn

from app.agents.resume.agent_loop import ResumeAgentLoop
from app.agents.resume.run_lifecycle import ResumeRunLifecycle
from app.agents.resume.runner import ResumeAgentRunner
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
from app.runtime.pi_agent_openrouter import stream_openrouter
from app.types.stream import ResumeStreamEvent


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
        self.lifecycle = ResumeRunLifecycle(
            model_name_provider=openrouter_chat_model_name,
        )
        self.turn_context_builder = ResumeTurnContextBuilder(
            tool_stage=self.tool_stage,
        )
        self.runner = ResumeAgentRunner(
            agent_loop=self.agent_loop,
            turn_context_builder=self.turn_context_builder,
            lifecycle=self.lifecycle,
            model_name_provider=openrouter_chat_model_name,
        )

    async def run(
        self,
        agent: AgentDefinition,
        user_message: str,
        context: dict[str, Any],
        conversation_history: list[dict[str, str]] | None = None,
        event_callback: RuntimeEventCallback | None = None,
    ) -> dict[str, Any]:
        """用于兼容 runtime 接口，并委托 Resume Agent runner 执行。"""
        return await self.runner.run(
            agent=agent,
            user_message=user_message,
            context=context,
            conversation_history=conversation_history,
            event_callback=event_callback,
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
        """用于兼容 runtime 接口，并委托 Resume Agent runner 返回事件流。"""
        async for event in self.runner.run_stream(
            agent=agent,
            user_message=user_message,
            context=context,
            conversation_history=conversation_history,
            confirmation_queue=confirmation_queue,
            event_callback=event_callback,
        ):
            yield event

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
        """用于兼容旧测试入口，并委托 run lifecycle 创建状态。"""
        return ResumeRunLifecycle.new_stream_state()

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
        """用于兼容旧测试入口，并委托 run lifecycle 生成响应事件。"""
        return self.lifecycle.llm_response_event(agent, state)

    def _prompt_rendered_event(
        self,
        agent: AgentDefinition,
        system_prompt: str,
        user_message: str,
    ) -> ResumeStreamEvent:
        """用于兼容旧测试入口，并委托 run lifecycle 生成 prompt 事件。"""
        return self.lifecycle.prompt_rendered_event(agent, system_prompt, user_message)

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
        """用于兼容旧测试入口，并委托 run lifecycle 记录开始。"""
        self.lifecycle.trace_run_start(
            agent,
            run_id,
            mode,
            user_message,
            conversation_history,
        )

    def _trace_prompt(
        self,
        agent: AgentDefinition,
        run_id: str,
        system_prompt: str,
    ) -> None:
        """用于兼容旧测试入口，并委托 run lifecycle 记录 prompt。"""
        self.lifecycle.trace_prompt(agent, run_id, system_prompt)

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
        """用于兼容旧测试入口，并委托 run lifecycle 记录响应。"""
        self.lifecycle.trace_llm_response(agent, run_id, event)

    def _trace_run_completed(
        self,
        agent: AgentDefinition,
        run_id: str,
        mode: str,
        state: dict[str, Any],
    ) -> None:
        """用于兼容旧测试入口，并委托 run lifecycle 记录完成。"""
        self.lifecycle.trace_run_completed(agent, run_id, mode, state)

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
        """用于兼容旧测试入口，并委托 run lifecycle 记录摘要。"""
        self.lifecycle.log_run_summary(
            agent=agent,
            run_id=run_id,
            mode=mode,
            state=state,
            success=success,
            error_type=error_type,
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
        """用于兼容旧测试入口，并委托 run lifecycle 发布事件。"""
        await ResumeRunLifecycle.publish_event(
            event_queue=event_queue,
            event_callback=event_callback,
            event=event,
        )

    @staticmethod
    def _emit_event(
        event_callback: RuntimeEventCallback | None,
        event: ResumeStreamEvent,
    ) -> None:
        """用于兼容旧测试入口，并委托 run lifecycle 发送事件。"""
        ResumeRunLifecycle.emit_event(event_callback, event)

    @staticmethod
    def _preview_text(value: Any, limit: int = 240) -> str:
        """用于兼容旧测试入口，并委托工具执行阶段生成预览。"""
        return ResumeToolExecutionStage.preview_text(value, limit=limit)

    @staticmethod
    def _trace(message: str, **fields: Any) -> None:
        """用于兼容旧测试入口，并委托 run lifecycle 记录 trace。"""
        ResumeRunLifecycle.trace(message, **fields)

    @staticmethod
    def _trace_chunk(message: str, **fields: Any) -> None:
        """用于兼容旧测试入口，并委托 run lifecycle 记录 chunk trace。"""
        ResumeRunLifecycle.trace_chunk(message, **fields)

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
