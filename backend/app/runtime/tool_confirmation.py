"""用于集中处理 Agent 工具确认等待规则。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass


@dataclass(frozen=True)
class ToolConfirmationDecision:
    """用于表达工具调用确认策略的判断结果。"""

    requires_confirmation: bool
    terminate_turn: bool = False


@dataclass(frozen=True)
class ToolConfirmationResult:
    """用于表达用户确认后的策略结果。"""

    confirmed: bool
    terminate_turn: bool


class ToolConfirmationPolicy:
    """用于封装工具确认 hook 语义。"""

    def before_tool_call(
        self,
        *,
        confirmation_queue: asyncio.Queue | None,
        tool_name: str,
        auto_execute_tool_names: set[str],
    ) -> ToolConfirmationDecision:
        """用于在工具执行前判断是否需要确认。"""
        return ToolConfirmationDecision(
            requires_confirmation=requires_tool_confirmation(
                confirmation_queue=confirmation_queue,
                tool_name=tool_name,
                auto_execute_tool_names=auto_execute_tool_names,
            )
        )

    async def wait_for_decision(self, confirmation_queue: asyncio.Queue) -> bool:
        """用于等待用户确认结果。"""
        return await wait_for_tool_confirmation(confirmation_queue)

    def after_tool_decision(self, *, confirmed: bool) -> ToolConfirmationResult:
        """用于在用户确认或拒绝后决定当前轮次是否应终止。"""
        return ToolConfirmationResult(confirmed=confirmed, terminate_turn=True)


def requires_tool_confirmation(
    *,
    confirmation_queue: asyncio.Queue | None,
    tool_name: str,
    auto_execute_tool_names: set[str],
) -> bool:
    """用于判断一个业务工具调用是否需要用户确认。"""
    return (
        confirmation_queue is not None
        and tool_name not in auto_execute_tool_names
    )


async def wait_for_tool_confirmation(
    confirmation_queue: asyncio.Queue,
    *,
    timeout_seconds: int = 300,
) -> bool:
    """用于等待用户确认，超时按拒绝处理。"""
    try:
        return bool(
            await asyncio.wait_for(
                confirmation_queue.get(),
                timeout=timeout_seconds,
            )
        )
    except asyncio.TimeoutError:
        return False


__all__ = [
    "ToolConfirmationDecision",
    "ToolConfirmationPolicy",
    "ToolConfirmationResult",
    "requires_tool_confirmation",
    "wait_for_tool_confirmation",
]
