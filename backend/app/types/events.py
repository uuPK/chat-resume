"""用于集中定义 runtime、存储和传输共用的事件名。"""

from typing import Final

AGENT_EVENT_TYPES: Final[tuple[str, ...]] = (
    "user_message",
    "agent_response_delta",
    "agent_response",
    "tool_call_previewed",
    "tool_call_confirmed",
    "tool_call_rejected",
    "tool_call_finished",
    "tool_call_failed",
    "checkpoint_saved",
    "session_failed",
    "session_completed",
)

__all__ = ["AGENT_EVENT_TYPES"]
