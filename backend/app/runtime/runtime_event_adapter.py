"""用于隔离 runtime 事件发布和可见事件适配。"""

from __future__ import annotations

import asyncio
from typing import Any

from app.runtime.contracts import RuntimeEventCallback
from app.types.stream import ResumeStreamEvent


async def publish_runtime_event(
    *,
    event_queue: asyncio.Queue[Any] | None,
    event_callback: RuntimeEventCallback | None,
    event: ResumeStreamEvent,
) -> None:
    """用于同时发布 runtime callback 和可选 SSE 队列事件。"""
    emit_runtime_event(event_callback, event)
    if event_queue is not None:
        await event_queue.put(event)


def emit_runtime_event(
    event_callback: RuntimeEventCallback | None,
    event: ResumeStreamEvent,
) -> None:
    """用于向可观测性 callback 发布 runtime 事件。"""
    if event_callback is not None:
        event_callback(event)


__all__ = ["emit_runtime_event", "publish_runtime_event"]
