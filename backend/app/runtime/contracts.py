"""用于定义业务 Agent 和运行时之间的共享契约。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Callable

from app.prompts import AgentPromptSpec

ToolExecutor = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]
PromptContextBuilder = Callable[[dict[str, Any]], dict[str, Any]]
RuntimeEventCallback = Callable[[Mapping[str, Any]], None]


@dataclass(slots=True)
class AgentDefinition:
    """Describes a business agent independently of a concrete runtime kernel."""

    prompt_spec: AgentPromptSpec
    tools_schema: list[dict[str, Any]]
    tool_executor: ToolExecutor
    prompt_context_builder: PromptContextBuilder
    max_iterations: int | None = None
    max_history_messages: int = 20
    auto_execute_tool_names: set[str] = field(default_factory=set)
    default_tool_profile: str = "resume_edit"
    tool_profiles: dict[str, set[str]] = field(default_factory=dict)


__all__ = [
    "AgentDefinition",
    "PromptContextBuilder",
    "RuntimeEventCallback",
    "ToolExecutor",
]
