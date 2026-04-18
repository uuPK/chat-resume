"""用于按用户维度读写长期记忆 Markdown 文件。"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from app.infra.config import settings


def build_default_user_memory_template() -> str:
    """用于生成新用户长期记忆文件的默认 Markdown 模板。"""
    return (
        "# 长期记忆\n\n"
        "## 用户画像\n"
        "- 暂无记录\n\n"
        "## 写作偏好\n"
        "- 暂无记录\n\n"
        "## 简历策略\n"
        "- 暂无记录\n\n"
        "## 已确认事实\n"
        "- 暂无记录\n"
    )


class UserMemoryService:
    """用于把每个用户的长期记忆隔离到独立 Markdown 文件中。"""

    def __init__(self, base_dir: str | None = None):
        """用于初始化长期记忆根目录。"""
        resolved = base_dir or settings.USER_MEMORY_DIR
        self.base_dir = Path(resolved)

    def get_memory_path(self, user_id: int) -> Path:
        """用于根据用户 id 定位该用户的长期记忆文件。"""
        return self.base_dir / str(user_id) / "MEMORY.md"

    def read_memory(self, user_id: int) -> dict[str, object]:
        """用于读取当前用户的长期记忆 Markdown 内容。"""
        path = self.get_memory_path(user_id)
        if not path.exists():
            return {
                "success": True,
                "exists": False,
                "content": build_default_user_memory_template(),
                "memory_file": self._logical_memory_file(user_id),
            }
        content = path.read_text(encoding="utf-8")
        return {
            "success": True,
            "exists": True,
            "content": content,
            "memory_file": self._logical_memory_file(user_id),
        }

    def write_memory(self, user_id: int, content: str) -> dict[str, object]:
        """用于把当前用户的长期记忆完整写回 Markdown 文件。"""
        normalized = self._normalize_markdown(content)
        path = self.get_memory_path(user_id)
        existed_before = path.exists()
        path.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write(path, normalized)
        return {
            "success": True,
            "exists": existed_before,
            "content": normalized,
            "memory_file": self._logical_memory_file(user_id),
            "bytes_written": len(normalized.encode("utf-8")),
        }

    def _normalize_markdown(self, content: str) -> str:
        """用于统一整理写入前的 Markdown 文本格式。"""
        normalized = content.replace("\r\n", "\n").strip()
        if not normalized:
            raise ValueError("长期记忆内容不能为空")
        if not normalized.startswith("#"):
            normalized = f"# 长期记忆\n\n{normalized}"
        return f"{normalized}\n"

    def _atomic_write(self, path: Path, content: str) -> None:
        """用于通过原子替换方式写入长期记忆文件。"""
        temp_path = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
        temp_path.write_text(content, encoding="utf-8")
        temp_path.replace(path)

    @staticmethod
    def _logical_memory_file(user_id: int) -> str:
        """用于返回对模型更稳定的逻辑记忆文件路径。"""
        return f"memory/users/{user_id}/MEMORY.md"
