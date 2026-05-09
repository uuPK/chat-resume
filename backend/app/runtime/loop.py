"""Runtime contracts and Deep Agents compatibility entrypoint.

Deep Agents is the only execution kernel for business agents.  This module keeps
the stable `AgentDefinition` contract and a small `AgentRuntime` compatibility
wrapper for older imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Callable

from app.prompts import AgentPromptSpec

ToolExecutor = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]
PromptContextBuilder = Callable[[dict[str, Any]], dict[str, Any]]
RuntimeEventCallback = Callable[[dict[str, Any]], None]


@dataclass(slots=True)
class AgentDefinition:
    """Describes a business agent independently of a concrete runtime kernel."""

    prompt_spec: AgentPromptSpec
    tools_schema: list[dict[str, Any]]
    tool_executor: ToolExecutor
    prompt_context_builder: PromptContextBuilder
    max_iterations: int = 6
    max_history_messages: int = 20
    auto_execute_tool_names: set[str] = field(default_factory=set)


class AgentRuntime:
    """Compatibility wrapper that delegates all execution to DeepAgentRuntime."""

    def __init__(self, model: Any | None = None):
        from app.runtime.deepagents_runtime import DeepAgentRuntime

        self._runtime = DeepAgentRuntime(model=model)

    async def run(
        self,
        agent: AgentDefinition,
        user_message: str,
        context: dict[str, Any],
        conversation_history: list[dict[str, str]] | None = None,
        event_callback: RuntimeEventCallback | None = None,
    ) -> dict[str, Any]:
        return await self._runtime.run(
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
        confirmation_queue: Any | None = None,
        event_callback: RuntimeEventCallback | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        async for event in self._runtime.run_stream(
            agent=agent,
            user_message=user_message,
            context=context,
            conversation_history=conversation_history,
            confirmation_queue=confirmation_queue,
            event_callback=event_callback,
        ):
            yield event


__all__ = [
    "AgentDefinition",
    "AgentRuntime",
    "PromptContextBuilder",
    "RuntimeEventCallback",
    "ToolExecutor",
]
