"""用于定义 Pi runtime 到 LLM 消息的显式转换边界。"""

from __future__ import annotations

from typing import Any

from pi_agent_core.types import AssistantMessage, Message, ToolResultMessage, UserMessage

_LLM_MESSAGE_TYPES = (UserMessage, AssistantMessage, ToolResultMessage)
_LLM_ROLES = {"user", "assistant", "toolResult"}


def convert_resume_messages_to_llm(messages: list[Any]) -> list[Message]:
    """用于过滤不会进入模型上下文的内部消息。"""
    converted: list[Message] = []
    for message in messages:
        if _is_internal_message(message):
            continue
        if isinstance(message, _LLM_MESSAGE_TYPES):
            converted.append(message)
            continue
        if getattr(message, "role", None) in _LLM_ROLES:
            converted.append(message)
    return converted


def _is_internal_message(message: Any) -> bool:
    """用于识别只供 UI、审计或恢复使用的内部消息。"""
    if bool(getattr(message, "internal_only", False)):
        return True
    metadata = getattr(message, "metadata", None)
    if isinstance(metadata, dict) and metadata.get("internal_only"):
        return True
    return getattr(message, "role", None) not in _LLM_ROLES


__all__ = ["convert_resume_messages_to_llm"]
