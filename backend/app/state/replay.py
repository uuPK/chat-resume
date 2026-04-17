"""用于把持久化事件还原成便于消费的历史列表。"""

from __future__ import annotations

from typing import Any

from app.state.models import AgentEvent


def replay_event_payloads(events: list[AgentEvent]) -> list[dict[str, Any]]:
    """用于把数据库事件对象转换成前端或调试可读的字典结构。"""
    payloads: list[dict[str, Any]] = []
    for event in events:
        payload = event.payload if isinstance(event.payload, dict) else {}
        payloads.append(
            {
                "sequence": event.sequence,
                "event_type": event.event_type,
                "source": event.source,
                "payload": payload,
            }
        )
    return payloads


__all__ = ["replay_event_payloads"]
