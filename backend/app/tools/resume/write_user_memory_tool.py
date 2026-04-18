"""用于覆盖写入当前用户长期记忆 Markdown 文件的工具实现。"""

from __future__ import annotations

from app.services.memory import UserMemoryService


def write_user_memory(
    *,
    user_id: int,
    content: str,
    memory_service: UserMemoryService | None = None,
) -> dict[str, object]:
    """用于把模型整理后的长期记忆完整写回当前用户文件。"""
    service = memory_service or UserMemoryService()
    result = service.write_memory(user_id, content)
    return {
        "success": True,
        "memory_file": result["memory_file"],
        "content": result["content"],
        "bytes_written": result["bytes_written"],
        "message": "已更新当前用户长期记忆",
    }
