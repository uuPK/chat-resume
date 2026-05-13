"""用于集中处理 Agent 工具确认等待规则。"""

from __future__ import annotations

import asyncio


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


__all__ = ["requires_tool_confirmation", "wait_for_tool_confirmation"]
