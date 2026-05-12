"""用于隔离 Deep Agents 与 LangChain 工具对象之间的适配逻辑。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, cast

from langchain_core.tools import ArgsSchema, StructuredTool


ToolCoroutine = Callable[..., Awaitable[str]]


def structured_tool_args_schema(value: Any) -> ArgsSchema:
    """用于把 OpenAI JSON tool parameters 转成 LangChain args_schema。"""
    if isinstance(value, dict):
        return cast(dict[str, Any], value)
    return {"type": "object", "properties": {}}


def make_deepagent_structured_tool(
    *,
    name: str,
    description: str,
    parameters: Any,
    coroutine: ToolCoroutine,
) -> StructuredTool:
    """用于把业务工具协程包装成 Deep Agents 可消费的 StructuredTool。"""
    return StructuredTool.from_function(
        coroutine=cast(Any, coroutine),
        name=name,
        description=description,
        args_schema=cast(Any, structured_tool_args_schema(parameters)),
        infer_schema=False,
    )


__all__ = ["make_deepagent_structured_tool", "structured_tool_args_schema"]
