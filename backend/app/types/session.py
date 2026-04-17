"""用于定义前端可直接读取的 session 快照类型。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class PendingAction:
    """用于描述当前等待用户处理的动作。"""

    type: str
    tool_name: str
    call_id: str
    summary: str
    input: dict[str, Any] | None = None


@dataclass(slots=True)
class LatestSummary:
    """用于承载当前 session 最近的高层摘要。"""

    text: str
    updated_at: str | None = None


@dataclass(slots=True)
class ResumableStep:
    """用于记录当前 session 可以恢复的执行位置。"""

    kind: str
    call_id: str | None = None
    event_sequence: int | None = None


@dataclass(slots=True)
class SessionSnapshot:
    """用于承载前端最关心的 session 当前快照。"""

    status: str
    pending_action: PendingAction | None = None
    latest_summary: LatestSummary | None = None
    resumable_step: ResumableStep | None = None

    def as_dict(self) -> dict[str, Any]:
        """用于把快照对象转换成便于传输的字典。"""
        return asdict(self)


__all__ = [
    "LatestSummary",
    "PendingAction",
    "ResumableStep",
    "SessionSnapshot",
]
