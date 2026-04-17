"""用于实现项目简介更新工具。"""

from __future__ import annotations

from typing import Any

from .shared import (
    SECTION_NAMES,
    build_diff_payload,
    find_item,
    normalize_reason,
    snapshot,
    summarize_dict,
)


def update_overview(
    resume_content: dict[str, Any],
    section: str,
    item_id: str,
    overview: Any,
    reason: Any = None,
) -> dict[str, Any]:
    """用于只修改项目条目的 overview 文本。"""
    if section != "projects":
        return {"success": False, "message": "只有 projects 支持 overview 编辑"}

    items, idx = find_item(resume_content, section, item_id)
    if items is None:
        return {"success": False, "message": f"{section} 数据格式异常"}
    if idx is None:
        return {"success": False, "message": f"未找到 id={item_id} 的条目"}

    next_overview = str(overview or "").strip()
    before = snapshot(items[idx])
    items[idx]["overview"] = next_overview
    resume_content[section] = items

    section_name = SECTION_NAMES.get(section, section)
    item_label = summarize_dict(items[idx])
    diff_payload = build_diff_payload(
        title=f"{section_name} / {item_label} 修改摘要",
        before=before.get("overview"),
        after=next_overview,
        reason=normalize_reason(reason),
    )
    return {
        "success": True,
        "message": f"已更新 {section_name} 的简介",
        "updated_section": section,
        **diff_payload,
    }


__all__ = ["update_overview"]
