"""用于实现新增亮点工具。"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from .shared import (
    HIGHLIGHT_SECTIONS,
    SECTION_NAMES,
    build_diff_payload,
    find_item,
    normalize_reason,
    summarize_dict,
)


def add_highlight(
    resume_content: dict[str, Any],
    section: str,
    item_id: str,
    text: Any,
    reason: Any = None,
) -> dict[str, Any]:
    """用于在指定条目下追加一条新的 highlight。"""
    if section not in HIGHLIGHT_SECTIONS:
        return {"success": False, "message": f"{section} 不支持亮点编辑"}

    items, idx = find_item(resume_content, section, item_id)
    if items is None:
        return {"success": False, "message": f"{section} 数据格式异常"}
    if idx is None:
        return {"success": False, "message": f"未找到 id={item_id} 的条目"}

    next_text = str(text or "").strip()
    if not next_text:
        return {"success": False, "message": "亮点文本不能为空"}

    highlight = {
        "id": f"{item_id}_hl_{uuid4().hex[:8]}",
        "text": next_text,
    }
    highlights = items[idx].get("highlights")
    if not isinstance(highlights, list):
        highlights = []
        items[idx]["highlights"] = highlights
    highlights.append(highlight)
    resume_content[section] = items

    section_name = SECTION_NAMES.get(section, section)
    item_label = summarize_dict(items[idx])
    diff_payload = build_diff_payload(
        title=f"{section_name} / {item_label} 新增亮点",
        before="（新增）",
        after=highlight,
        reason=normalize_reason(reason),
    )
    return {
        "success": True,
        "message": f"已在 {section_name} 中新增亮点",
        "updated_section": section,
        **diff_payload,
    }


__all__ = ["add_highlight"]
