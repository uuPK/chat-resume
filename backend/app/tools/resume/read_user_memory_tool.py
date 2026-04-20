"""用于读取当前用户长期记忆 Markdown 文件的工具实现。"""

from __future__ import annotations

from app.services.memory import UserMemoryService


def read_user_memory(
    *,
    user_id: int,
    memory_service: UserMemoryService | None = None,
) -> dict[str, object]:
    """用于返回当前用户的长期记忆内容给模型继续推理。"""
    service = memory_service or UserMemoryService()
    result = service.read_memory(user_id)
    exists = bool(result.get("exists"))
    content = str(result.get("content", "") or "")
    return {
        "success": True,
        "memory_file": result["memory_file"],
        "exists": exists,
        "content": content,
        "message": "已读取当前用户长期记忆"
        if exists
        else "当前用户还没有长期记忆，已返回默认模板",
    }
