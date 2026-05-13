"""pi-agent-core backed runtime for business agents."""

from __future__ import annotations

import asyncio
import json
import logging
from copy import deepcopy
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
    MessageEndEvent,
    MessageUpdateEvent,
    Model,
    TextContent,
    ToolCall,
    ToolExecutionStartEvent,
    UserMessage,
    agent_loop,
)
from pi_agent_core.types import Message, StreamFn

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
from app.infra.config import settings
from app.infra.otel_setup import record_exception, set_span_attribute, start_span
from app.runtime.contracts import AgentDefinition, RuntimeEventCallback
from app.runtime.tool_confirmation import (
    requires_tool_confirmation,
    wait_for_tool_confirmation,
)
from app.runtime.runtime_event_adapter import (
    emit_runtime_event,
    publish_runtime_event,
)
from app.runtime.pi_agent_openrouter import stream_openrouter
from app.types.stream import ResumeStreamEvent

logger = logging.getLogger(__name__)

_SENTINEL = object()


class PiAgentRuntime:
    """Runtime adapter that uses pi-agent-core as the execution loop."""

    def __init__(self, stream_fn: StreamFn | None = None):
        """Initialize with an optional stream function for tests or providers."""
        self.stream_fn = stream_fn or stream_openrouter

    async def run(
        self,
        agent: AgentDefinition,
        user_message: str,
        context: dict[str, Any],
        conversation_history: list[dict[str, str]] | None = None,
        event_callback: RuntimeEventCallback | None = None,
    ) -> dict[str, Any]:
        """Execute one full pi-agent-core turn and return final text."""
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
        )
        self._trace_run_start(agent, run_id, "sync", user_message, conversation_history)
        self._trace_prompt(agent, run_id, pi_context.system_prompt)
        self._emit_event(
            event_callback,
            self._prompt_rendered_event(agent, pi_context.system_prompt, user_message),
        )
        request_event = self._llm_request_event(agent, pi_context, prompts)
        self._trace_llm_request(agent, run_id, request_event)
        self._emit_event(event_callback, request_event)
        async for event in agent_loop(
            prompts,
            pi_context,
            config,
            stream_fn=self.stream_fn,
        ):
            await self._handle_pi_event(
                event=event,
                event_queue=None,
                event_callback=event_callback,
                agent=agent,
                run_id=run_id,
                state=state,
            )
        response_event = self._llm_response_event(agent, state)
        self._trace_llm_response(agent, run_id, response_event)
        self._emit_event(event_callback, response_event)
        self._trace_run_completed(agent, run_id, "sync", state)
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
        """Stream pi-agent-core model output and business tool events."""
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
        )
        self._trace_run_start(agent, run_id, "stream", user_message, conversation_history)
        self._trace_prompt(agent, run_id, pi_context.system_prompt)
        prompt_event = self._prompt_rendered_event(
            agent,
            pi_context.system_prompt,
            user_message,
        )
        request_event = self._llm_request_event(agent, pi_context, prompts)
        self._trace_llm_request(agent, run_id, request_event)
        self._emit_event(event_callback, prompt_event)
        self._emit_event(event_callback, request_event)
        yield prompt_event
        yield request_event

        producer = asyncio.create_task(
            self._produce_stream_events(
                agent=agent,
                run_id=run_id,
                pi_context=pi_context,
                prompts=prompts,
                config=config,
                event_queue=event_queue,
                event_callback=event_callback,
                state=state,
            )
        )
        while True:
            event = await event_queue.get()
            if event is _SENTINEL:
                break
            yield event
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
        event_queue: asyncio.Queue[Any],
        event_callback: RuntimeEventCallback | None,
        state: dict[str, Any],
    ) -> None:
        """Run pi-agent-core in the background and forward visible events."""
        try:
            async for event in agent_loop(
                prompts,
                pi_context,
                config,
                stream_fn=self.stream_fn,
            ):
                await self._handle_pi_event(
                    event=event,
                    event_queue=event_queue,
                    event_callback=event_callback,
                    agent=agent,
                    run_id=run_id,
                    state=state,
                )
        finally:
            response_event = self._llm_response_event(agent, state)
            self._trace_llm_response(agent, run_id, response_event)
            await self._publish_event(
                event_queue=event_queue,
                event_callback=event_callback,
                event=response_event,
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
    ) -> tuple[AgentContext, list[Message], AgentLoopConfig]:
        """Build pi-agent-core context, prompt messages, and loop config."""
        prompt_context = agent.prompt_context_builder(context)
        system_prompt = agent.prompt_spec.render(**prompt_context)
        tools = self._build_tools(
            agent=agent,
            context=context,
            confirmation_queue=confirmation_queue,
            event_queue=event_queue,
            event_callback=event_callback,
            run_id=run_id,
            executed_tools=executed_tools,
        )
        pi_context = AgentContext(
            system_prompt=system_prompt,
            messages=self._history_messages(
                conversation_history,
                agent.max_history_messages,
            ),
            tools=tools,
        )
        prompts: list[Message] = [UserMessage(content=[TextContent(text=user_message)])]
        config = AgentLoopConfig(
            model=self._build_model(),
            reasoning=None,
            api_key=settings.OPENROUTER_API_KEY,
            temperature=agent.prompt_spec.model_defaults.get("temperature", 0.3),
            max_tokens=agent.prompt_spec.model_defaults.get("max_tokens", 1500),
            convert_to_llm=lambda messages: messages,
        )
        return pi_context, prompts, config

    def _build_tools(
        self,
        *,
        agent: AgentDefinition,
        context: dict[str, Any],
        confirmation_queue: asyncio.Queue | None,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        run_id: str,
        executed_tools: list[dict[str, Any]],
    ) -> list[AgentTool]:
        """Convert OpenAI-style business tool schemas into pi-agent-core tools."""
        tools: list[AgentTool] = []
        lock = asyncio.Lock()
        for schema in agent.tools_schema:
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
    ) -> AgentTool:
        """Wrap one business tool for pi-agent-core execution."""

        async def execute(
            tool_call_id: str,
            params: dict[str, Any],
            *_args: Any,
        ) -> AgentToolResult:
            """Execute one pi-agent-core tool call through the business executor."""
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
    ) -> AgentToolResult:
        """Run a business tool and return a pi-agent-core tool result."""
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
    ) -> str:
        """Execute one business tool with preview and confirmation events."""
        tool_started_at = perf_counter()
        needs_confirmation = requires_tool_confirmation(
            confirmation_queue=confirmation_queue,
            tool_name=tool_name,
            auto_execute_tool_names=agent.auto_execute_tool_names,
        )
        tool_call = self._tool_call_payload(call_id, tool_name, tool_input)
        await self._publish_visible_tool_call(
            call_id=call_id,
            tool_name=tool_name,
            tool_input=tool_input,
            event_queue=event_queue,
            event_callback=event_callback,
        )
        self._trace_tool_requested(
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
    ) -> dict[str, Any] | str | None:
        """Publish preview events and return a rejection payload when rejected."""
        if not needs_confirmation:
            return None
        assert confirmation_queue is not None
        preview_context = {"resume_content": deepcopy(context.get("resume_content"))}
        preview_result = agent.tool_executor(tool_call, preview_context)
        diff_summary = preview_result.get("display_message") or "执行完成"
        result = preview_result.get("result", {})
        diff_items = result.get("diff_items", []) if isinstance(result, dict) else []
        self._trace_tool_preview(agent, run_id, call_id, tool_name, preview_result)
        await self._publish_event(
            event_queue=event_queue,
            event_callback=event_callback,
            event=tool_pending_event(
                call_id=call_id,
                tool_id=tool_name,
                tool_call=tool_call,
                tool_display_name=preview_result["tool_name"],
                tool_input=tool_input,
                diff_summary=diff_summary,
                diff_items=diff_items,
                tool_calls=executed_tools,
            ),
        )
        confirmed = await wait_for_tool_confirmation(confirmation_queue)
        self._trace_tool_confirmation(
            agent,
            run_id,
            call_id,
            tool_name,
            preview_result["tool_name"],
            confirmed,
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
    ) -> str:
        """Run the confirmed business tool and publish the result event."""
        with start_span(
            "agent.tool",
            {
                "agent.name": agent.prompt_spec.name,
                "agent.run_id": run_id,
                "tool.name": tool_name,
                "tool.call_id": call_id,
            },
        ) as span:
            try:
                tool_result = agent.tool_executor(tool_call, context)
            except Exception as exc:
                record_exception(span, exc)
                raise
            set_span_attribute(span, "tool.confirmation_required", needs_confirmation)
        result = tool_result.get("result", {})
        display_message = tool_result.get("display_message")
        self._trace_tool_executed(
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

    async def _handle_pi_event(
        self,
        *,
        event: Any,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        agent: AgentDefinition,
        run_id: str,
        state: dict[str, Any],
    ) -> None:
        """Translate pi-agent-core events into the existing resume stream events."""
        if isinstance(event, MessageUpdateEvent):
            await self._handle_message_update(
                event=event,
                event_queue=event_queue,
                event_callback=event_callback,
                agent=agent,
                run_id=run_id,
                state=state,
            )
            return
        if isinstance(event, ToolExecutionStartEvent):
            self._trace_tool_call_detected(agent, run_id, event)
            return
        if isinstance(event, MessageEndEvent) and isinstance(event.message, AssistantMessage):
            state["last_assistant_text"] = self._assistant_text(event.message)

    async def _handle_message_update(
        self,
        *,
        event: MessageUpdateEvent,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        agent: AgentDefinition,
        run_id: str,
        state: dict[str, Any],
    ) -> None:
        """Publish text deltas from pi-agent-core message update events."""
        raw = event.assistant_message_event
        if getattr(raw, "type", None) != "text_delta":
            return
        content = str(getattr(raw, "delta", "") or "")
        if not content:
            return
        state["chunk_index"] += 1
        state["response_parts"].append(content)
        self._trace(
            "agent.trace.intermediate.chunk",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            chunk_index=state["chunk_index"],
            content_preview=self._preview_text(content),
            content_chars=len(content),
        )
        await self._publish_event(
            event_queue=event_queue,
            event_callback=event_callback,
            event=text_delta_event(content=content),
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
        """Publish a visible tool-call start event before business execution."""
        tool_call = self._tool_call_payload(call_id, tool_name, tool_input)
        await self._publish_event(
            event_queue=event_queue,
            event_callback=event_callback,
            event=tool_call_event(
                call_id=call_id,
                tool_id=tool_name,
                tool_call=tool_call,
                tool_display_name=tool_name,
                tool_input=tool_call["function"]["arguments"],
                display_message=f"正在{tool_name}",
                tool_calls=[],
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
        """Publish success or failure events for a finished business tool."""
        if self._is_tool_failure(tool_result):
            event = tool_call_failed_event(
                call_id=call_id,
                tool_id=tool_name,
                tool_display_name=tool_result["tool_name"],
                tool_calls=executed_tools,
                result=result,
                display_message=display_message,
            )
        elif needs_confirmation:
            event = tool_confirmed_event(
                call_id=call_id,
                tool_id=tool_name,
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
            event = tool_result_event(
                call_id=call_id,
                tool_id=tool_name,
                tool_display_name=tool_result["tool_name"],
                tool_calls=executed_tools,
                result=result,
                display_message=display_message,
                context=context,
            )
        await self._publish_event(
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
        """Publish a rejected confirmation event and trace record."""
        self._trace(
            "agent.trace.tool.rejected",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            call_id=call_id,
            tool_name=tool_name,
            tool_display_name=tool_display_name,
            latency_ms=round((perf_counter() - tool_started_at) * 1000, 2),
        )
        await self._publish_event(
            event_queue=event_queue,
            event_callback=event_callback,
            event=tool_rejected_event(
                call_id=call_id,
                tool_id=tool_name,
                tool_display_name=tool_display_name,
                diff_summary=diff_summary,
                diff_items=diff_items,
                result=result,
                tool_calls=executed_tools,
            ),
        )

    def _build_model(self) -> Model:
        """Build the pi-agent-core model identifier for OpenRouter."""
        return Model(api="openai-compatible", provider="openrouter", id=settings.OPENROUTER_MODEL)

    @staticmethod
    def _tool_schema(value: Any) -> AgentToolSchema:
        """Convert an OpenAI parameters object into a pi-agent-core schema."""
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
        """Convert stored chat history into pi-agent-core messages."""
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
        """Build the local OpenAI-style tool-call payload."""
        return {
            "id": call_id,
            "type": "function",
            "function": {"name": tool_name, "arguments": tool_input},
        }

    @staticmethod
    def _new_stream_state() -> dict[str, Any]:
        """Create mutable per-run stream accounting state."""
        return {
            "started_at": perf_counter(),
            "chunk_index": 0,
            "response_parts": [],
            "last_assistant_text": "",
        }

    def _llm_request_event(
        self,
        agent: AgentDefinition,
        context: AgentContext,
        prompts: list[Message],
    ) -> ResumeStreamEvent:
        """Build an internal LLM request event for observability."""
        messages = [self._message_to_dict(message) for message in context.messages + prompts]
        return llm_request_event(
            agent_name=agent.prompt_spec.name,
            model=self._chat_model_name(),
            messages=[{"role": "system", "content": context.system_prompt}, *messages],
            params={
                "temperature": agent.prompt_spec.model_defaults.get("temperature", 0.3),
                "max_tokens": agent.prompt_spec.model_defaults.get("max_tokens", 1500),
            },
            tool_names=self._optional_tool_names(agent),
        )

    def _llm_response_event(
        self,
        agent: AgentDefinition,
        state: dict[str, Any],
    ) -> ResumeStreamEvent:
        """Build an internal LLM response event for observability."""
        return llm_response_event(
            agent_name=agent.prompt_spec.name,
            model=self._chat_model_name(),
            response_content="".join(state["response_parts"]),
            tool_call_count=0,
            latency_ms=round((perf_counter() - state["started_at"]) * 1000, 2),
        )

    @staticmethod
    def _prompt_rendered_event(
        agent: AgentDefinition,
        system_prompt: str,
        user_message: str,
    ) -> ResumeStreamEvent:
        """Build an internal prompt-rendered event."""
        return prompt_rendered_event(
            agent_name=agent.prompt_spec.name,
            system_prompt=system_prompt,
            user_message_preview=str(user_message)[:1500],
        )

    @staticmethod
    def _message_to_dict(message: Message) -> dict[str, Any]:
        """Convert one pi-agent-core message into a compact trace dict."""
        role = getattr(message, "role", "unknown")
        content = PiAgentRuntime._assistant_text(message)
        return {"role": role, "content": content}

    @staticmethod
    def _assistant_text(message: Any) -> str:
        """Return concatenated text content from a pi-agent-core message."""
        parts = []
        for block in getattr(message, "content", []):
            if isinstance(block, TextContent):
                parts.append(block.text)
        return "".join(parts)

    def _trace_run_start(
        self,
        agent: AgentDefinition,
        run_id: str,
        mode: str,
        user_message: str,
        conversation_history: list[dict[str, str]] | None,
    ) -> None:
        """Trace the beginning of one runtime turn."""
        self._trace(
            "agent.trace.run.started",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            mode=mode,
            user_message_preview=self._preview_text(user_message),
            history_count=len(conversation_history or []),
            tool_names=self._tool_names(agent),
        )

    def _trace_prompt(
        self,
        agent: AgentDefinition,
        run_id: str,
        system_prompt: str,
    ) -> None:
        """Trace rendered prompt size."""
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
        """Trace the model request metadata for one agent turn."""
        self._trace(
            "agent.trace.llm.request",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            model=self._chat_model_name(),
            message_count=len(event.get("messages", [])),
            tool_names=event.get("tool_names", []),
            params=event.get("params", {}),
        )

    def _trace_llm_response(
        self,
        agent: AgentDefinition,
        run_id: str,
        event: ResumeStreamEvent,
    ) -> None:
        """Trace the model response metadata for one agent turn."""
        self._trace(
            "agent.trace.llm.response",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            model=self._chat_model_name(),
            response_preview=self._preview_text(event.get("response_content")),
            response_chars=len(str(event.get("response_content") or "")),
            latency_ms=event.get("latency_ms"),
        )

    def _trace_run_completed(
        self,
        agent: AgentDefinition,
        run_id: str,
        mode: str,
        state: dict[str, Any],
    ) -> None:
        """Trace the end of one runtime turn."""
        self._trace(
            "agent.trace.run.completed",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            mode=mode,
            latency_ms=round((perf_counter() - state["started_at"]) * 1000, 2),
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
        """Trace a requested business tool call."""
        self._trace(
            "agent.trace.tool.requested",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            call_id=call_id,
            tool_name=tool_name,
            tool_input=self._safe_tool_input(tool_input),
            requires_confirmation=needs_confirmation,
        )

    def _trace_tool_preview(
        self,
        agent: AgentDefinition,
        run_id: str,
        call_id: str,
        tool_name: str,
        preview_result: dict[str, Any],
    ) -> None:
        """Trace generated tool preview information."""
        result = preview_result.get("result", {})
        diff_items = result.get("diff_items", []) if isinstance(result, dict) else []
        self._trace(
            "agent.trace.tool.preview",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            call_id=call_id,
            tool_name=tool_name,
            tool_display_name=preview_result["tool_name"],
            diff_summary=self._preview_text(preview_result.get("display_message")),
            diff_item_count=len(diff_items),
            result_success=self._tool_success(preview_result),
        )

    def _trace_tool_confirmation(
        self,
        agent: AgentDefinition,
        run_id: str,
        call_id: str,
        tool_name: str,
        display_name: str,
        confirmed: bool,
    ) -> None:
        """Trace the user's confirmation decision."""
        self._trace(
            "agent.trace.tool.confirmation",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            call_id=call_id,
            tool_name=tool_name,
            tool_display_name=display_name,
            confirmed=confirmed,
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
        """Trace a completed business tool execution."""
        self._trace(
            "agent.trace.tool.executed",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            call_id=call_id,
            tool_name=tool_name,
            tool_display_name=tool_result["tool_name"],
            result_success=self._tool_success(tool_result),
            display_message=self._preview_text(tool_result.get("display_message")),
            result_summary=self._result_summary(tool_result.get("result", {})),
            latency_ms=round((perf_counter() - tool_started_at) * 1000, 2),
        )

    def _trace_tool_call_detected(
        self,
        agent: AgentDefinition,
        run_id: str,
        event: ToolExecutionStartEvent,
    ) -> None:
        """Trace the first visible model tool call for the turn."""
        self._trace(
            "agent.trace.reasoning.tool_call_detected",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            tool_call_count=1,
            tool_call_chunk_count=1,
            tool_names=[event.tool_name],
        )

    @staticmethod
    async def _publish_event(
        *,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        event: ResumeStreamEvent,
    ) -> None:
        """Publish a runtime event to callback and optional stream queue."""
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
        """Emit a runtime event to the callback only."""
        emit_runtime_event(event_callback, event)

    @staticmethod
    def _executed_tool_summary(
        tool_result: dict[str, Any],
        result: Any,
    ) -> dict[str, Any]:
        """Return the compact executed-tool summary used by the UI."""
        return {
            "name": tool_result["tool_name"],
            "result": result.get("diff_summary") if isinstance(result, dict) else tool_result.get("display_message"),
        }

    @staticmethod
    def _is_tool_failure(tool_result: dict[str, Any]) -> bool:
        """Return whether a tool result is an explicit business failure."""
        result = tool_result.get("result")
        return isinstance(result, dict) and result.get("success") is False

    @staticmethod
    def _tool_success(tool_result: dict[str, Any]) -> bool | None:
        """Return explicit success value from a business tool result."""
        result = tool_result.get("result")
        if isinstance(result, dict) and "success" in result:
            return bool(result["success"])
        return None

    @classmethod
    def _result_summary(cls, result: Any) -> dict[str, Any]:
        """Build a safe compact result summary for logs."""
        if not isinstance(result, dict):
            return {"type": type(result).__name__, "preview": cls._preview_text(result)}
        summary: dict[str, Any] = {"keys": sorted(str(key) for key in result.keys())}
        if "success" in result:
            summary["success"] = result.get("success")
        if "diff_summary" in result:
            summary["diff_summary"] = cls._preview_text(result.get("diff_summary"))
        if isinstance(result.get("diff_items"), list):
            summary["diff_item_count"] = len(result["diff_items"])
        if "error" in result:
            summary["error"] = cls._preview_text(result.get("error"))
        return summary

    @classmethod
    def _safe_tool_input(cls, tool_input: dict[str, Any]) -> dict[str, Any]:
        """Remove large or sensitive fields from tool-call trace payloads."""
        return {
            key: cls._summarize_value(value)
            for key, value in tool_input.items()
            if key not in {"resume_content", "content"}
        }

    @classmethod
    def _summarize_value(cls, value: Any) -> Any:
        """Summarize nested values for structured logs."""
        if isinstance(value, str):
            return cls._preview_text(value)
        if isinstance(value, (int, float, bool)) or value is None:
            return value
        if isinstance(value, list):
            return {"type": "list", "count": len(value)}
        if isinstance(value, dict):
            return {"type": "dict", "keys": sorted(str(key) for key in value.keys())[:20]}
        return {"type": type(value).__name__, "preview": cls._preview_text(value)}

    @staticmethod
    def _preview_text(value: Any, limit: int = 240) -> str:
        """Return a single-line bounded text preview."""
        if value is None:
            return ""
        text = " ".join(str(value).split())
        if len(text) <= limit:
            return text
        return f"{text[:limit]}..."

    @staticmethod
    def _trace(message: str, **fields: Any) -> None:
        """Emit an agent trace log when trace logging is enabled."""
        if not settings.AGENT_TRACE_LOG_ENABLED:
            return
        logger.info(message, extra={"agent_trace": True, **fields})

    @staticmethod
    def _tool_names(agent: AgentDefinition) -> list[str]:
        """Return configured business tool names."""
        names: list[str] = []
        for schema in agent.tools_schema:
            name = schema.get("function", {}).get("name")
            if isinstance(name, str) and name:
                names.append(name)
        return names

    @staticmethod
    def _optional_tool_names(agent: AgentDefinition) -> list[str | None]:
        """Return configured business tool names for stream event payloads."""
        return list(PiAgentRuntime._tool_names(agent))

    @staticmethod
    def _chat_model_name() -> str:
        """Return the configured chat model name."""
        return settings.OPENROUTER_MODEL


__all__ = ["PiAgentRuntime"]
