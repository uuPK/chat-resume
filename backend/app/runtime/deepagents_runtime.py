"""Deep Agents backed runtime for business agents."""

from __future__ import annotations

import asyncio
import json
import logging
from copy import deepcopy
from time import perf_counter
from typing import Any, AsyncGenerator, cast
from uuid import uuid4

from deepagents import create_deep_agent
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI

from app.infra.config import settings
from app.runtime.loop import AgentDefinition, RuntimeEventCallback

logger = logging.getLogger(__name__)

_SENTINEL = object()


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
        prompt_context = agent.prompt_context_builder(context)
        system_prompt = agent.prompt_spec.render(**prompt_context)
        self._emit_prompt_rendered(
            agent=agent,
            system_prompt=system_prompt,
            user_message=user_message,
            event_callback=event_callback,
        )

        tools = self._build_tools(
            agent=agent,
            context=context,
            confirmation_queue=None,
            event_queue=None,
            event_callback=event_callback,
        )
        deep_agent = create_deep_agent(
            model=self._build_model(agent),
            tools=tools,
            system_prompt=system_prompt,
            name=agent.prompt_spec.name,
        )
        started_at = perf_counter()
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
        self._emit_event(
            event_callback,
            {
                "event_type": "llm_response",
                "agent_name": agent.prompt_spec.name,
                "model": self._chat_model_name(),
                "content": final_text,
                "tool_calls": [],
                "latency_ms": round((perf_counter() - started_at) * 1000, 2),
            },
        )
        return {"content": final_text, "tool_calls": [], "context": context}

    async def run_stream(
        self,
        agent: AgentDefinition,
        user_message: str,
        context: dict[str, Any],
        conversation_history: list[dict[str, str]] | None = None,
        confirmation_queue: asyncio.Queue | None = None,
        event_callback: RuntimeEventCallback | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream Deep Agents model output and custom business tool events."""
        prompt_context = agent.prompt_context_builder(context)
        system_prompt = agent.prompt_spec.render(**prompt_context)
        prompt_event = self._prompt_rendered_event(
            agent=agent,
            system_prompt=system_prompt,
            user_message=user_message,
        )
        self._emit_event(event_callback, prompt_event)
        yield prompt_event

        request_event = {
            "internal_only": True,
            "llm_request": True,
            "agent_name": agent.prompt_spec.name,
            "model": self._chat_model_name(),
            "messages": [
                {"role": "system", "content": system_prompt},
                *self._build_messages(
                    user_message=user_message,
                    conversation_history=conversation_history,
                    max_history_messages=agent.max_history_messages,
                ),
            ],
            "params": {
                "temperature": agent.prompt_spec.model_defaults.get(
                    "temperature",
                    0.3,
                ),
                "max_tokens": agent.prompt_spec.model_defaults.get(
                    "max_tokens",
                    1500,
                ),
            },
            "tool_names": [
                tool.get("function", {}).get("name") for tool in agent.tools_schema
            ],
            "done": False,
        }
        self._emit_event(event_callback, request_event)
        yield request_event

        event_queue: asyncio.Queue[Any] = asyncio.Queue()
        tools = self._build_tools(
            agent=agent,
            context=context,
            confirmation_queue=confirmation_queue,
            event_queue=event_queue,
            event_callback=event_callback,
        )
        deep_agent = create_deep_agent(
            model=self._build_model(agent),
            tools=tools,
            system_prompt=system_prompt,
            name=agent.prompt_spec.name,
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
            )
        )

        while True:
            event = await event_queue.get()
            if event is _SENTINEL:
                break
            yield event

        await producer

    async def _produce_stream_events(
        self,
        *,
        deep_agent: Any,
        messages: list[dict[str, Any]],
        context: dict[str, Any],
        event_queue: asyncio.Queue[Any],
        agent_name: str,
        event_callback: RuntimeEventCallback | None,
    ) -> None:
        """Forward Deep Agents message stream into the local event queue."""
        started_at = perf_counter()
        response_parts: list[str] = []
        try:
            async for message, metadata in deep_agent.astream(
                cast(Any, {"messages": messages}),
                stream_mode="messages",
            ):
                if metadata.get("langgraph_node") != "model":
                    continue
                if self._message_has_tool_calls(message):
                    continue
                content = self._coerce_content_text(getattr(message, "content", ""))
                if not content:
                    continue
                response_parts.append(content)
                await event_queue.put(
                    {
                        "content": content,
                        "tool_calls": [],
                        "context": None,
                        "done": False,
                    }
                )
        finally:
            response_text = "".join(response_parts)
            response_event = {
                "internal_only": True,
                "llm_response": True,
                "agent_name": agent_name,
                "model": self._chat_model_name(),
                "response_content": response_text,
                "tool_call_count": 0,
                "latency_ms": round((perf_counter() - started_at) * 1000, 2),
                "done": False,
            }
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
    ) -> list[StructuredTool]:
        """Convert OpenAI-style tool schemas into LangChain structured tools."""
        tools: list[StructuredTool] = []
        executed_tools: list[dict[str, Any]] = []

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
                    tool_name=__tool_name,
                    tool_input=kwargs,
                    context=context,
                    confirmation_queue=confirmation_queue,
                    event_queue=event_queue,
                    event_callback=event_callback,
                    executed_tools=executed_tools,
                )

            tools.append(
                StructuredTool.from_function(
                    coroutine=run_tool,
                    name=tool_name,
                    description=str(function.get("description", "")),
                    args_schema=function.get("parameters") or {
                        "type": "object",
                        "properties": {},
                    },
                    infer_schema=False,
                )
            )

        return tools

    async def _execute_tool(
        self,
        *,
        agent: AgentDefinition,
        tool_name: str,
        tool_input: dict[str, Any],
        context: dict[str, Any],
        confirmation_queue: asyncio.Queue | None,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        executed_tools: list[dict[str, Any]],
    ) -> str:
        """Run a business tool, preserving existing preview and confirmation events."""
        call_id = uuid4().hex
        tool_call = {
            "id": call_id,
            "type": "function",
            "function": {"name": tool_name, "arguments": tool_input},
        }

        if (
            confirmation_queue is not None
            and tool_name not in agent.auto_execute_tool_names
        ):
            preview_context = {
                "resume_content": deepcopy(context.get("resume_content"))
            }
            preview_result = agent.tool_executor(tool_call, preview_context)
            diff_summary = preview_result.get("display_message") or "执行完成"
            diff_items = preview_result.get("result", {}).get("diff_items", [])
            pending_event = {
                "content": "",
                "tool_pending": True,
                "call_id": call_id,
                "tool_call": tool_call,
                "tool_name": preview_result["tool_name"],
                "tool_input": tool_input,
                "diff_summary": diff_summary,
                "diff_items": diff_items,
                "tool_calls": executed_tools,
                "done": False,
            }
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

            if not confirmed:
                rejected_result = {"success": False, "error": "用户拒绝了此修改"}
                rejected_event = {
                    "content": "",
                    "tool_rejected": True,
                    "call_id": call_id,
                    "tool_name": preview_result["tool_name"],
                    "diff_summary": diff_summary,
                    "diff_items": diff_items,
                    "result": rejected_result,
                    "tool_calls": executed_tools,
                    "done": False,
                }
                await self._publish_event(
                    event_queue=event_queue,
                    event_callback=event_callback,
                    event=rejected_event,
                )
                return json.dumps(rejected_result, ensure_ascii=False)

        tool_result = agent.tool_executor(tool_call, context)
        display_message = tool_result.get("display_message")
        result = tool_result.get("result", {})
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
            failed_event = {
                "content": "",
                "tool_call_failed": True,
                "call_id": call_id,
                "tool_name": tool_result["tool_name"],
                "tool_calls": executed_tools,
                "result": result,
                "display_message": display_message,
                "done": False,
            }
            await self._publish_event(
                event_queue=event_queue,
                event_callback=event_callback,
                event=failed_event,
            )
            return json.dumps(result, ensure_ascii=False)

        event_key = (
            "tool_confirmed"
            if confirmation_queue is not None
            and tool_name not in agent.auto_execute_tool_names
            else None
        )
        if event_key:
            result_event = {
                "content": "",
                event_key: True,
                "call_id": call_id,
                "tool_name": tool_result["tool_name"],
                "tool_calls": executed_tools,
                "qr_images": (
                    [tool_result["qr_image"]] if tool_result.get("qr_image") else []
                ),
                "result": result,
                "display_message": display_message,
                "diff_summary": result.get("diff_summary")
                if isinstance(result, dict)
                else None,
                "diff_items": result.get("diff_items", [])
                if isinstance(result, dict)
                else [],
                "context": context,
                "done": False,
            }
        else:
            result_event = {
                "content": "",
                "tool_calls": executed_tools,
                "result": result,
                "display_message": display_message,
                "context": context,
                "done": False,
            }
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
            "default_headers": {
                "HTTP-Referer": "https://chat-resume.com",
                "X-Title": "Chat Resume AI Assistant",
            },
        }
        return ChatOpenAI(**model_config)

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
    ) -> dict[str, Any]:
        return {
            "internal_only": True,
            "prompt_rendered": True,
            "agent_name": agent.prompt_spec.name,
            "system_prompt": system_prompt,
            "user_message_preview": str(user_message)[:1500],
            "done": False,
        }

    async def _publish_event(
        self,
        *,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        event: dict[str, Any],
    ) -> None:
        self._emit_event(event_callback, event)
        if event_queue is not None:
            await event_queue.put(event)

    @staticmethod
    def _emit_event(
        event_callback: RuntimeEventCallback | None,
        event: dict[str, Any],
    ) -> None:
        if event_callback is not None:
            event_callback(event)

    @staticmethod
    def _message_has_tool_calls(message: Any) -> bool:
        return bool(getattr(message, "tool_calls", None)) or bool(
            getattr(message, "tool_call_chunks", None)
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

    def _chat_model_name(self) -> str:
        model = self.model
        if model is not None:
            return str(getattr(model, "model_name", getattr(model, "model", model)))
        return settings.OPENROUTER_MODEL


__all__ = ["DeepAgentRuntime"]
