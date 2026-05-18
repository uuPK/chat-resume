"""用于实现个人总结更新工具。"""

from __future__ import annotations

from typing import Any

from .shared import build_diff_payload, normalize_reason, snapshot


def update_summary(
    resume_content: dict[str, Any],
    text: Any,
    reason: Any = None,
) -> dict[str, Any]:
    """用于更新简历个人总结文本。"""
    next_text = str(text or "").strip()
    if not next_text:
        return {"success": False, "message": "个人总结不能为空"}

    summary = resume_content.get("summary")
    if not isinstance(summary, dict):
        summary = {}

    before = snapshot(summary)
    summary["text"] = next_text
    resume_content["summary"] = summary

    diff_payload = build_diff_payload(
        title="个人总结 修改内容",
        before=before.get("text") if isinstance(before, dict) else before,
        after=next_text,
        reason=normalize_reason(reason),
    )
    return {
        "success": True,
        "message": "已更新个人总结",
        "updated_section": "summary",
        **diff_payload,
    }


__all__ = ["update_summary"]
