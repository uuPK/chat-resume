"""Deep Agents backed runtime for business agents."""

from __future__ import annotations

import asyncio
import json
import logging
from collections import deque
from copy import deepcopy
from pathlib import Path
from time import perf_counter
from typing import Any, AsyncGenerator, cast
from uuid import uuid4

from langchain_core.tools import ArgsSchema, StructuredTool
from langchain_openai import ChatOpenAI

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
from app.infra.warnings_setup import suppress_noisy_dependency_warnings
from app.runtime.contracts import AgentDefinition, RuntimeEventCallback
from app.runtime.deepagents_profile import configure_deepagents_harness_profile
from app.types.stream import ResumeStreamEvent

suppress_noisy_dependency_warnings()
from deepagents import create_deep_agent  # noqa: E402
from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend  # noqa: E402
from deepagents.middleware.filesystem import FilesystemPermission  # noqa: E402

configure_deepagents_harness_profile()

logger = logging.getLogger(__name__)

_SENTINEL = object()
_MEMORY_ROUTE = "/memories/"
_MEMORY_FILE = f"{_MEMORY_ROUTE}AGENTS.md"
_INTERNAL_TOOL_DISPLAY_NAMES = {
    "read_file": "读取记忆",
    "write_file": "写入记忆",
    "edit_file": "更新记忆",
    "write_todos": "更新计划",
    "task": "调用子代理",
    "update_highlight": "update_bullet",
    "add_highlight": "add_bullet",
    "remove_highlight": "remove_bullet",
}
_DEFAULT_MEMORY_CONTENT = (
    "# AGENTS.md\n\n"
    "## 用户偏好\n"
    "- 暂无记录\n\n"
    "## 简历策略\n"
    "- 暂无记录\n\n"
    "## 已确认事实\n"
    "- 暂无记录\n"
)


class DeepAgentRuntime:
    """Runtime adapter that uses Deep Agents as the model/tool execution core."""

    def __init__(self, model: Any | None = None):
        """Initialize with an optional LangChain chat model for tests or overrides."""
        self.model = model

    async def run(
        self,
        agent: AgentDefinition,
        user_message: str,
        context: dict[str, Any],
        conversation_history: list[dict[str, str]] | None = None,
        event_callback: RuntimeEventCallback | None = None,
    ) -> dict[str, Any]:
        """Execute one full Deep Agents turn and return the final assistant text."""
        run_id = uuid4().hex
        started_at = perf_counter()
        self._trace(
            "agent.trace.run.started",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            mode="sync",
            user_message_preview=self._preview_text(user_message),
            history_count=len(conversation_history or []),
            tool_names=self._tool_names(agent),
        )
        prompt_context = agent.prompt_context_builder(context)
        system_prompt = agent.prompt_spec.render(**prompt_context)
        self._trace(
            "agent.trace.prompt.rendered",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            prompt_chars=len(system_prompt),
            prompt_context_keys=sorted(prompt_context.keys()),
        )
        self._emit_prompt_rendered(
            agent=agent,
            system_prompt=system_prompt,
            user_message=user_message,
            event_callback=event_callback,
        )

        executed_tools: list[dict[str, Any]] = []
        tools = self._build_tools(
            agent=agent,
            context=context,
            confirmation_queue=None,
            event_queue=None,
            event_callback=event_callback,
            run_id=run_id,
            executed_tools=executed_tools,
            model_tool_call_ids_by_name=None,
        )
        deep_agent = self._create_deep_agent(
            agent=agent,
            tools=tools,
            system_prompt=system_prompt,
            context=context,
        )
        self._trace(
            "agent.trace.llm.request",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            model=self._chat_model_name(),
            message_count=len(conversation_history or []) + 1,
            tool_names=self._tool_names(agent),
            params={
                "temperature": agent.prompt_spec.model_defaults.get(
                    "temperature",
                    0.3,
                ),
                "max_tokens": agent.prompt_spec.model_defaults.get(
                    "max_tokens",
                    1500,
                ),
            },
        )
        result = await deep_agent.ainvoke(
            cast(
                Any,
                {
                    "messages": self._build_messages(
                        user_message=user_message,
                        conversation_history=conversation_history,
                        max_history_messages=agent.max_history_messages,
                    )
                },
            )
        )
        final_text = self._last_assistant_text(result.get("messages", []))
        latency_ms = round((perf_counter() - started_at) * 1000, 2)
        self._trace(
            "agent.trace.run.completed",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            mode="sync",
            response_preview=self._preview_text(final_text),
            response_chars=len(final_text),
            latency_ms=latency_ms,
        )
        self._emit_event(
            event_callback,
            {
                "event_type": "llm_response",
                "agent_name": agent.prompt_spec.name,
                "model": self._chat_model_name(),
                "content": final_text,
                "tool_calls": [],
                "latency_ms": latency_ms,
            },
        )
        return {"content": final_text, "tool_calls": executed_tools, "context": context}

    async def run_stream(
        self,
        agent: AgentDefinition,
        user_message: str,
        context: dict[str, Any],
        conversation_history: list[dict[str, str]] | None = None,
        confirmation_queue: asyncio.Queue | None = None,
        event_callback: RuntimeEventCallback | None = None,
    ) -> AsyncGenerator[ResumeStreamEvent, None]:
        """Stream Deep Agents model output and custom business tool events."""
        run_id = uuid4().hex
        run_started_at = perf_counter()
        self._trace(
            "agent.trace.run.started",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            mode="stream",
            user_message_preview=self._preview_text(user_message),
            history_count=len(conversation_history or []),
            tool_names=self._tool_names(agent),
        )
        prompt_context = agent.prompt_context_builder(context)
        system_prompt = agent.prompt_spec.render(**prompt_context)
        self._trace(
            "agent.trace.prompt.rendered",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            prompt_chars=len(system_prompt),
            prompt_context_keys=sorted(prompt_context.keys()),
        )
        prompt_event = self._prompt_rendered_event(
            agent=agent,
            system_prompt=system_prompt,
            user_message=user_message,
        )
        self._emit_event(event_callback, prompt_event)
        yield prompt_event

        request_event = llm_request_event(
            agent_name=agent.prompt_spec.name,
            model=self._chat_model_name(),
            messages=[
                {"role": "system", "content": system_prompt},
                *self._build_messages(
                    user_message=user_message,
                    conversation_history=conversation_history,
                    max_history_messages=agent.max_history_messages,
                ),
            ],
            params={
                "temperature": agent.prompt_spec.model_defaults.get(
                    "temperature",
                    0.3,
                ),
                "max_tokens": agent.prompt_spec.model_defaults.get(
                    "max_tokens",
                    1500,
                ),
            },
            tool_names=[
                tool.get("function", {}).get("name") for tool in agent.tools_schema
            ],
        )
        self._trace(
            "agent.trace.llm.request",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            model=self._chat_model_name(),
            message_count=len(request_event.get("messages", [])),
            tool_names=request_event.get("tool_names", []),
            params=request_event.get("params", {}),
        )
        self._emit_event(event_callback, request_event)
        yield request_event

        event_queue: asyncio.Queue[Any] = asyncio.Queue()
        model_tool_call_ids_by_name: dict[str, deque[str]] = {}
        tools = self._build_tools(
            agent=agent,
            context=context,
            confirmation_queue=confirmation_queue,
            event_queue=event_queue,
            event_callback=event_callback,
            run_id=run_id,
            model_tool_call_ids_by_name=model_tool_call_ids_by_name,
        )
        deep_agent = self._create_deep_agent(
            agent=agent,
            tools=tools,
            system_prompt=system_prompt,
            context=context,
        )
        messages = self._build_messages(
            user_message=user_message,
            conversation_history=conversation_history,
            max_history_messages=agent.max_history_messages,
        )
        producer = asyncio.create_task(
            self._produce_stream_events(
                deep_agent=deep_agent,
                messages=messages,
                context=context,
                event_queue=event_queue,
                agent_name=agent.prompt_spec.name,
                event_callback=event_callback,
                run_id=run_id,
                model_tool_call_ids_by_name=model_tool_call_ids_by_name,
            )
        )

        while True:
            event = await event_queue.get()
            if event is _SENTINEL:
                break
            yield event

        await producer
        self._trace(
            "agent.trace.run.completed",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            mode="stream",
            latency_ms=round((perf_counter() - run_started_at) * 1000, 2),
        )

    async def _produce_stream_events(
        self,
        *,
        deep_agent: Any,
        messages: list[dict[str, Any]],
        context: dict[str, Any],
        event_queue: asyncio.Queue[Any],
        agent_name: str,
        event_callback: RuntimeEventCallback | None,
        run_id: str,
        model_tool_call_ids_by_name: dict[str, deque[str]],
    ) -> None:
        """Forward Deep Agents message stream into the local event queue."""
        started_at = perf_counter()
        response_parts: list[str] = []
        chunk_index = 0
        tool_call_detected = False
        seen_tool_call_keys: set[str] = set()
        seen_tool_calls: dict[str, dict[str, Any]] = {}
        try:
            async for message, metadata in deep_agent.astream(
                cast(Any, {"messages": messages}),
                stream_mode="messages",
            ):
                if metadata.get("langgraph_node") != "model":
                    tool_result = self._visible_tool_result_event(
                        message=message,
                        seen_tool_calls=seen_tool_calls,
                    )
                    if tool_result is not None:
                        await self._publish_event(
                            event_queue=event_queue,
                            event_callback=event_callback,
                            event=tool_result,
                        )
                        continue
                    logger.debug(
                        "agent.trace.intermediate.skipped",
                        extra={
                            "agent_trace": True,
                            "run_id": run_id,
                            "agent_name": agent_name,
                            "langgraph_node": metadata.get("langgraph_node"),
                            "reason": "non_model_node",
                        },
                    )
                    continue
                if self._message_has_tool_calls(message):
                    tool_calls = self._coerce_tool_calls(message)
                    if not tool_call_detected:
                        tool_call_detected = True
                        tool_call_chunks = (
                            getattr(message, "tool_call_chunks", []) or []
                        )
                        self._trace(
                            "agent.trace.reasoning.tool_call_detected",
                            run_id=run_id,
                            agent_name=agent_name,
                            tool_call_count=len(tool_calls),
                            tool_call_chunk_count=len(tool_call_chunks),
                            tool_names=[
                                call.get("name")
                                for call in tool_calls
                                if isinstance(call, dict)
                            ],
                        )
                    for tool_call in tool_calls:
                        tool_call_key = self._tool_call_key(tool_call)
                        if tool_call_key in seen_tool_call_keys:
                            continue
                        seen_tool_call_keys.add(tool_call_key)
                        seen_tool_calls[tool_call_key] = tool_call
                        tool_name = self._tool_call_name(tool_call)
                        if tool_name:
                            model_tool_call_ids_by_name.setdefault(
                                tool_name,
                                deque(),
                            ).append(tool_call_key)
                        if not self._should_surface_model_tool_call(tool_call):
                            continue
                        await self._publish_event(
                            event_queue=event_queue,
                            event_callback=event_callback,
                            event=self._visible_tool_call_event(
                                tool_call=tool_call,
                            ),
                        )
                    continue
                content = self._coerce_content_text(getattr(message, "content", ""))
                if not content:
                    logger.debug(
                        "agent.trace.intermediate.skipped",
                        extra={
                            "agent_trace": True,
                            "run_id": run_id,
                            "agent_name": agent_name,
                            "reason": "empty_content",
                        },
                    )
                    continue
                chunk_index += 1
                response_parts.append(content)
                self._trace(
                    "agent.trace.intermediate.chunk",
                    run_id=run_id,
                    agent_name=agent_name,
                    chunk_index=chunk_index,
                    content_preview=self._preview_text(content),
                    content_chars=len(content),
                )
                await event_queue.put(text_delta_event(content=content))
        finally:
            response_text = "".join(response_parts)
            latency_ms = round((perf_counter() - started_at) * 1000, 2)
            self._trace(
                "agent.trace.llm.response",
                run_id=run_id,
                agent_name=agent_name,
                model=self._chat_model_name(),
                response_preview=self._preview_text(response_text),
                response_chars=len(response_text),
                chunk_count=chunk_index,
                latency_ms=latency_ms,
            )
            response_event = llm_response_event(
                agent_name=agent_name,
                model=self._chat_model_name(),
                response_content=response_text,
                tool_call_count=len(seen_tool_call_keys),
                latency_ms=latency_ms,
            )
            self._emit_event(event_callback, response_event)
            await event_queue.put(response_event)
            await event_queue.put(_SENTINEL)

    def _build_tools(
        self,
        *,
        agent: AgentDefinition,
        context: dict[str, Any],
        confirmation_queue: asyncio.Queue | None,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        run_id: str,
        executed_tools: list[dict[str, Any]] | None = None,
        model_tool_call_ids_by_name: dict[str, deque[str]] | None = None,
    ) -> list[StructuredTool]:
        """Convert OpenAI-style tool schemas into LangChain structured tools."""
        tools: list[StructuredTool] = []
        tool_results = executed_tools if executed_tools is not None else []
        confirmation_state: dict[str, Any] = {
            "business_tool_lock": asyncio.Lock(),
        }

        for schema in agent.tools_schema:
            function = schema.get("function", {})
            tool_name = function.get("name")
            if not isinstance(tool_name, str) or not tool_name:
                continue

            async def run_tool(
                __tool_name: str = tool_name,
                **kwargs: Any,
            ) -> str:
                return await self._execute_tool(
                    agent=agent,
                    run_id=run_id,
                    tool_name=__tool_name,
                    tool_input=kwargs,
                    context=context,
                    confirmation_queue=confirmation_queue,
                    event_queue=event_queue,
                    event_callback=event_callback,
                    executed_tools=tool_results,
                    confirmation_state=confirmation_state,
                    model_tool_call_ids_by_name=model_tool_call_ids_by_name,
                )

            tools.append(
                StructuredTool.from_function(
                    coroutine=run_tool,
                    name=tool_name,
                    description=str(function.get("description", "")),
                    args_schema=cast(
                        Any,
                        self._structured_tool_args_schema(function.get("parameters")),
                    ),
                    infer_schema=False,
                )
            )

        return tools

    @staticmethod
    def _structured_tool_args_schema(value: Any) -> ArgsSchema:
        """Coerce OpenAI JSON tool parameters into LangChain's args schema type."""
        if isinstance(value, dict):
            return cast(dict[str, Any], value)
        return {"type": "object", "properties": {}}

    async def _execute_tool(
        self,
        *,
        agent: AgentDefinition,
        run_id: str,
        tool_name: str,
        tool_input: dict[str, Any],
        context: dict[str, Any],
        confirmation_queue: asyncio.Queue | None,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        executed_tools: list[dict[str, Any]],
        confirmation_state: dict[str, Any] | None = None,
        model_tool_call_ids_by_name: dict[str, deque[str]] | None = None,
    ) -> str:
        """Run a business tool, serializing resume mutation tools per agent turn."""
        if (
            confirmation_state is not None
            and tool_name not in agent.auto_execute_tool_names
        ):
            lock = confirmation_state["business_tool_lock"]
            async with lock:
                return await self._execute_tool_locked(
                    agent=agent,
                    run_id=run_id,
                    tool_name=tool_name,
                    tool_input=tool_input,
                    context=context,
                    confirmation_queue=confirmation_queue,
                    event_queue=event_queue,
                    event_callback=event_callback,
                    executed_tools=executed_tools,
                    confirmation_state=confirmation_state,
                    model_tool_call_ids_by_name=model_tool_call_ids_by_name,
                )
        return await self._execute_tool_locked(
            agent=agent,
            run_id=run_id,
            tool_name=tool_name,
            tool_input=tool_input,
            context=context,
            confirmation_queue=confirmation_queue,
            event_queue=event_queue,
            event_callback=event_callback,
            executed_tools=executed_tools,
            confirmation_state=confirmation_state,
            model_tool_call_ids_by_name=model_tool_call_ids_by_name,
        )

    async def _execute_tool_locked(
        self,
        *,
        agent: AgentDefinition,
        run_id: str,
        tool_name: str,
        tool_input: dict[str, Any],
        context: dict[str, Any],
        confirmation_queue: asyncio.Queue | None,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        executed_tools: list[dict[str, Any]],
        confirmation_state: dict[str, Any] | None = None,
        model_tool_call_ids_by_name: dict[str, deque[str]] | None = None,
    ) -> str:
        """Run a business tool, preserving existing preview and confirmation events."""
        call_id = self._next_tool_call_id(
            tool_name=tool_name,
            model_tool_call_ids_by_name=model_tool_call_ids_by_name,
        )
        tool_started_at = perf_counter()
        requires_confirmation = (
            confirmation_queue is not None
            and tool_name not in agent.auto_execute_tool_names
        )
        tool_call = {
            "id": call_id,
            "type": "function",
            "function": {"name": tool_name, "arguments": tool_input},
        }
        self._trace(
            "agent.trace.tool.requested",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            call_id=call_id,
            tool_name=tool_name,
            tool_input=self._safe_tool_input(tool_input),
            requires_confirmation=requires_confirmation,
        )

        if requires_confirmation:
            assert confirmation_queue is not None
            preview_context = {
                "resume_content": deepcopy(context.get("resume_content"))
            }
            preview_result = agent.tool_executor(tool_call, preview_context)
            diff_summary = preview_result.get("display_message") or "执行完成"
            diff_items = preview_result.get("result", {}).get("diff_items", [])
            self._trace(
                "agent.trace.tool.preview",
                run_id=run_id,
                agent_name=agent.prompt_spec.name,
                call_id=call_id,
                tool_name=tool_name,
                tool_display_name=preview_result["tool_name"],
                diff_summary=self._preview_text(diff_summary),
                diff_item_count=len(diff_items),
                result_success=self._tool_success(preview_result),
            )
            pending_event = tool_pending_event(
                call_id=call_id,
                tool_id=tool_name,
                tool_call=tool_call,
                tool_display_name=preview_result["tool_name"],
                tool_input=tool_input,
                diff_summary=diff_summary,
                diff_items=diff_items,
                tool_calls=executed_tools,
            )
            await self._publish_event(
                event_queue=event_queue,
                event_callback=event_callback,
                event=pending_event,
            )

            try:
                confirmed = await asyncio.wait_for(
                    confirmation_queue.get(),
                    timeout=300,
                )
            except asyncio.TimeoutError:
                confirmed = False
            self._trace(
                "agent.trace.tool.confirmation",
                run_id=run_id,
                agent_name=agent.prompt_spec.name,
                call_id=call_id,
                tool_name=tool_name,
                tool_display_name=preview_result["tool_name"],
                confirmed=confirmed,
            )

            if not confirmed:
                rejected_result = {"success": False, "error": "用户拒绝了此修改"}
                self._trace(
                    "agent.trace.tool.rejected",
                    run_id=run_id,
                    agent_name=agent.prompt_spec.name,
                    call_id=call_id,
                    tool_name=tool_name,
                    tool_display_name=preview_result["tool_name"],
                    latency_ms=round((perf_counter() - tool_started_at) * 1000, 2),
                )
                rejected_event = tool_rejected_event(
                    call_id=call_id,
                    tool_id=tool_name,
                    tool_display_name=preview_result["tool_name"],
                    diff_summary=diff_summary,
                    diff_items=diff_items,
                    result=rejected_result,
                    tool_calls=executed_tools,
                )
                await self._publish_event(
                    event_queue=event_queue,
                    event_callback=event_callback,
                    event=rejected_event,
                )
                return json.dumps(rejected_result, ensure_ascii=False)

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
            set_span_attribute(span, "tool.confirmation_required", requires_confirmation)
        display_message = tool_result.get("display_message")
        result = tool_result.get("result", {})
        self._trace(
            "agent.trace.tool.executed",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            call_id=call_id,
            tool_name=tool_name,
            tool_display_name=tool_result["tool_name"],
            result_success=self._tool_success(tool_result),
            display_message=self._preview_text(display_message),
            result_summary=self._result_summary(result),
            latency_ms=round((perf_counter() - tool_started_at) * 1000, 2),
        )
        executed_tools.append(
            {
                "name": tool_result["tool_name"],
                "result": (
                    result.get("diff_summary")
                    if isinstance(result, dict)
                    else display_message
                ),
            }
        )

        if self._is_tool_failure(tool_result):
            failed_event = tool_call_failed_event(
                call_id=call_id,
                tool_id=tool_name,
                tool_display_name=tool_result["tool_name"],
                tool_calls=executed_tools,
                result=result,
                display_message=display_message,
            )
            await self._publish_event(
                event_queue=event_queue,
                event_callback=event_callback,
                event=failed_event,
            )
            return json.dumps(result, ensure_ascii=False)

        event_key = (
            "tool_confirmed"
            if requires_confirmation
            else None
        )
        if event_key:
            result_event = tool_confirmed_event(
                call_id=call_id,
                tool_id=tool_name,
                tool_display_name=tool_result["tool_name"],
                tool_calls=executed_tools,
                qr_images=(
                    [tool_result["qr_image"]] if tool_result.get("qr_image") else []
                ),
                result=result,
                display_message=display_message,
                diff_summary=result.get("diff_summary")
                if isinstance(result, dict)
                else None,
                diff_items=result.get("diff_items", [])
                if isinstance(result, dict)
                else [],
                context=context,
            )
        else:
            result_event = tool_result_event(
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
            event=result_event,
        )
        return json.dumps(result, ensure_ascii=False)

    def _build_model(self, agent: AgentDefinition) -> Any:
        """Build the LangChain chat model used by Deep Agents."""
        if self.model is not None:
            return self.model
        defaults = agent.prompt_spec.model_defaults
        model_config: dict[str, Any] = {
            "model": settings.OPENROUTER_MODEL,
            "api_key": settings.OPENROUTER_API_KEY,
            "base_url": settings.OPENROUTER_API_BASE,
            "temperature": defaults.get("temperature", 0.3),
            "max_completion_tokens": defaults.get("max_tokens", 1500),
            "timeout": settings.OPENROUTER_READ_TIMEOUT_SECONDS,
            "max_retries": settings.OPENROUTER_MAX_RETRIES,
            "model_kwargs": {"parallel_tool_calls": False},
            "default_headers": {
                "HTTP-Referer": "https://chat-resume.com",
                "X-Title": "Chat Resume AI Assistant",
            },
        }
        return ChatOpenAI(**model_config)

    def _create_deep_agent(
        self,
        *,
        agent: AgentDefinition,
        tools: list[Any],
        system_prompt: str,
        context: dict[str, Any] | None = None,
    ) -> Any:
        """Build a Deep Agents graph with the project harness profile applied."""
        memory_config = self._build_memory_config(context or {})
        return create_deep_agent(
            model=self._build_model(agent),
            tools=tools,
            system_prompt=system_prompt,
            memory=memory_config["memory"],
            backend=memory_config["backend"],
            permissions=memory_config["permissions"],
            name=agent.prompt_spec.name,
        )

    def _build_memory_config(self, context: dict[str, Any]) -> dict[str, Any]:
        """Configure official Deep Agents filesystem memory for a bound user."""
        user_id = context.get("user_id")
        if not isinstance(user_id, int):
            return {"memory": None, "backend": None, "permissions": None}

        memory_root = self._ensure_user_memory_file(user_id)
        backend = CompositeBackend(
            default=StateBackend(),
            routes={
                _MEMORY_ROUTE: FilesystemBackend(
                    root_dir=memory_root,
                    virtual_mode=True,
                )
            },
        )
        permissions = [
            FilesystemPermission(
                operations=["read", "write"],
                paths=[_MEMORY_FILE],
                mode="allow",
            ),
            FilesystemPermission(
                operations=["read", "write"],
                paths=["/**"],
                mode="deny",
            ),
        ]
        return {"memory": [_MEMORY_FILE], "backend": backend, "permissions": permissions}

    @staticmethod
    def _ensure_user_memory_file(user_id: int) -> str:
        """Create the official Deep Agents memory file for the current user."""
        memory_root = Path(settings.USER_MEMORY_DIR) / str(user_id)
        memory_path = memory_root / "AGENTS.md"
        if not memory_path.exists():
            memory_path.parent.mkdir(parents=True, exist_ok=True)
            memory_path.write_text(_DEFAULT_MEMORY_CONTENT, encoding="utf-8")
        return str(memory_root)

    @staticmethod
    def _build_messages(
        *,
        user_message: str,
        conversation_history: list[dict[str, str]] | None,
        max_history_messages: int,
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        if conversation_history:
            messages.extend(conversation_history[-max_history_messages:])
        messages.append({"role": "user", "content": user_message})
        return messages

    def _emit_prompt_rendered(
        self,
        *,
        agent: AgentDefinition,
        system_prompt: str,
        user_message: str,
        event_callback: RuntimeEventCallback | None,
    ) -> None:
        self._emit_event(
            event_callback,
            self._prompt_rendered_event(
                agent=agent,
                system_prompt=system_prompt,
                user_message=user_message,
            ),
        )

    @staticmethod
    def _prompt_rendered_event(
        *,
        agent: AgentDefinition,
        system_prompt: str,
        user_message: str,
    ) -> ResumeStreamEvent:
        return prompt_rendered_event(
            agent_name=agent.prompt_spec.name,
            system_prompt=system_prompt,
            user_message_preview=str(user_message)[:1500],
        )

    async def _publish_event(
        self,
        *,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        event: ResumeStreamEvent,
    ) -> None:
        self._emit_event(event_callback, event)
        if event_queue is not None:
            await event_queue.put(event)

    @staticmethod
    def _emit_event(
        event_callback: RuntimeEventCallback | None,
        event: ResumeStreamEvent,
    ) -> None:
        if event_callback is not None:
            event_callback(event)

    @staticmethod
    def _message_has_tool_calls(message: Any) -> bool:
        return bool(getattr(message, "tool_calls", None)) or bool(
            getattr(message, "tool_call_chunks", None)
        )

    @staticmethod
    def _coerce_tool_calls(message: Any) -> list[dict[str, Any]]:
        """Return complete model tool calls, ignoring partial streamed chunks."""
        tool_calls = getattr(message, "tool_calls", None) or []
        return [call for call in tool_calls if isinstance(call, dict)]

    @staticmethod
    def _tool_call_key(tool_call: dict[str, Any]) -> str:
        call_id = tool_call.get("id")
        if isinstance(call_id, str) and call_id:
            return call_id
        return json.dumps(tool_call, ensure_ascii=False, sort_keys=True, default=str)

    @staticmethod
    def _next_tool_call_id(
        *,
        tool_name: str,
        model_tool_call_ids_by_name: dict[str, deque[str]] | None,
    ) -> str:
        if model_tool_call_ids_by_name is None:
            return uuid4().hex
        call_ids = model_tool_call_ids_by_name.get(tool_name)
        if call_ids:
            return call_ids.popleft()
        return uuid4().hex

    @staticmethod
    def _tool_call_name(tool_call: dict[str, Any]) -> str:
        name = tool_call.get("name")
        if isinstance(name, str):
            return name
        function = tool_call.get("function")
        if isinstance(function, dict) and isinstance(function.get("name"), str):
            return function["name"]
        return ""

    @staticmethod
    def _tool_call_args(tool_call: dict[str, Any]) -> dict[str, Any]:
        args = tool_call.get("args")
        if isinstance(args, dict):
            return args
        function = tool_call.get("function")
        if not isinstance(function, dict):
            return {}
        raw_arguments = function.get("arguments")
        if isinstance(raw_arguments, dict):
            return raw_arguments
        if isinstance(raw_arguments, str) and raw_arguments.strip():
            try:
                parsed = json.loads(raw_arguments)
            except json.JSONDecodeError:
                return {}
            if isinstance(parsed, dict):
                return parsed
        return {}

    @classmethod
    def _should_surface_model_tool_call(cls, tool_call: dict[str, Any]) -> bool:
        return bool(cls._tool_call_name(tool_call))

    @classmethod
    def _visible_tool_call_event(
        cls,
        *,
        tool_call: dict[str, Any],
    ) -> ResumeStreamEvent:
        tool_name = cls._tool_call_name(tool_call)
        tool_input = cls._tool_call_args(tool_call)
        call_id = tool_call.get("id")
        if not isinstance(call_id, str) or not call_id:
            call_id = cls._tool_call_key(tool_call)
        display_name = _INTERNAL_TOOL_DISPLAY_NAMES.get(tool_name, tool_name)
        return tool_call_event(
            call_id=call_id,
            tool_id=tool_name,
            tool_call={
                "id": call_id,
                "type": "function",
                "function": {"name": tool_name, "arguments": tool_input},
            },
            tool_display_name=display_name,
            tool_input=tool_input,
            display_message=f"正在{display_name}",
            tool_calls=[],
        )

    @classmethod
    def _visible_tool_result_event(
        cls,
        *,
        message: Any,
        seen_tool_calls: dict[str, dict[str, Any]],
    ) -> ResumeStreamEvent | None:
        call_id = getattr(message, "tool_call_id", None)
        if not isinstance(call_id, str) or not call_id:
            return None

        tool_call = seen_tool_calls.get(call_id, {})
        tool_name = cls._tool_call_name(tool_call)
        if not tool_name:
            raw_name = getattr(message, "name", None)
            tool_name = raw_name if isinstance(raw_name, str) else ""
        if not tool_name:
            return None

        display_name = _INTERNAL_TOOL_DISPLAY_NAMES.get(tool_name, tool_name)
        return tool_result_event(
            call_id=call_id,
            tool_id=tool_name,
            tool_display_name=display_name,
            tool_calls=[],
            result={"content": cls._coerce_content_text(getattr(message, "content", ""))},
            display_message=None,
            context=None,
        )

    @classmethod
    def _last_assistant_text(cls, messages: list[Any]) -> str:
        for message in reversed(messages):
            if cls._message_has_tool_calls(message):
                continue
            content = cls._coerce_content_text(getattr(message, "content", ""))
            if content:
                return content
        return ""

    @staticmethod
    def _coerce_content_text(content: Any) -> str:
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            return "".join(parts)
        return str(content)

    @staticmethod
    def _is_tool_failure(tool_result: dict[str, Any]) -> bool:
        result = tool_result.get("result")
        return isinstance(result, dict) and result.get("success") is False

    @staticmethod
    def _trace(message: str, **fields: Any) -> None:
        if not settings.AGENT_TRACE_LOG_ENABLED:
            return
        logger.info(message, extra={"agent_trace": True, **fields})

    @staticmethod
    def _tool_names(agent: AgentDefinition) -> list[str]:
        names: list[str] = []
        for schema in agent.tools_schema:
            name = schema.get("function", {}).get("name")
            if isinstance(name, str) and name:
                names.append(name)
        return names

    @classmethod
    def _safe_tool_input(cls, tool_input: dict[str, Any]) -> dict[str, Any]:
        return {
            key: cls._summarize_value(value)
            for key, value in tool_input.items()
            if key not in {"resume_content", "content"}
        }

    @classmethod
    def _result_summary(cls, result: Any) -> dict[str, Any]:
        if not isinstance(result, dict):
            return {"type": type(result).__name__, "preview": cls._preview_text(result)}
        summary: dict[str, Any] = {
            "keys": sorted(str(key) for key in result.keys()),
        }
        if "success" in result:
            summary["success"] = result.get("success")
        if "diff_summary" in result:
            summary["diff_summary"] = cls._preview_text(result.get("diff_summary"))
        if isinstance(result.get("diff_items"), list):
            summary["diff_item_count"] = len(result["diff_items"])
        if "error" in result:
            summary["error"] = cls._preview_text(result.get("error"))
        return summary

    @staticmethod
    def _tool_success(tool_result: dict[str, Any]) -> bool | None:
        result = tool_result.get("result")
        if isinstance(result, dict) and "success" in result:
            return bool(result["success"])
        return None

    @classmethod
    def _summarize_value(cls, value: Any) -> Any:
        if isinstance(value, str):
            return cls._preview_text(value)
        if isinstance(value, (int, float, bool)) or value is None:
            return value
        if isinstance(value, list):
            return {
                "type": "list",
                "count": len(value),
                "sample": [cls._summarize_value(item) for item in value[:3]],
            }
        if isinstance(value, dict):
            return {
                "type": "dict",
                "keys": sorted(str(key) for key in value.keys())[:20],
            }
        return {"type": type(value).__name__, "preview": cls._preview_text(value)}

    @staticmethod
    def _preview_text(value: Any, limit: int = 240) -> str:
        if value is None:
            return ""
        text = " ".join(str(value).split())
        if len(text) <= limit:
            return text
        return f"{text[:limit]}..."

    def _chat_model_name(self) -> str:
        model = self.model
        if model is not None:
            return str(getattr(model, "model_name", getattr(model, "model", model)))
        return settings.OPENROUTER_MODEL


__all__ = ["DeepAgentRuntime"]
