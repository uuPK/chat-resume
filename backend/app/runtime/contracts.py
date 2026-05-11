"""Runtime contracts shared by business agents and execution kernels."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

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


__all__ = [
    "AgentDefinition",
    "PromptContextBuilder",
    "RuntimeEventCallback",
    "ToolExecutor",
]
