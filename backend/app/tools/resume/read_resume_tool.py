"""用于提供只读简历内容的工具实现。"""

from __future__ import annotations

from typing import Any


def read_resume_content(resume_content: dict[str, Any]) -> dict[str, Any]:
    """用于把当前简历内容原样返回给模型或上层调用方。"""
    return {"content": resume_content, "message": "已成功读取简历内容"}


__all__ = ["read_resume_content"]
