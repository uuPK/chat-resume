"""用于实现简历 bullet 文本更新工具。"""

from __future__ import annotations

from typing import Any

from .shared import (
    HIGHLIGHT_SECTIONS,
    SECTION_NAMES,
    build_diff_payload,
    find_item,
    normalize_reason,
    snapshot,
    summarize_dict,
)


def update_highlight(
    resume_content: dict[str, Any],
    section: str,
    item_id: str,
    highlight_id: str,
    text: Any,
    reason: Any = None,
) -> dict[str, Any]:
    """用于精确更新某条 resume bullet 的文本内容。"""
    if section not in HIGHLIGHT_SECTIONS:
        return {"success": False, "message": f"{section} 不支持要点编辑"}

    items, idx = find_item(resume_content, section, item_id)
    if items is None:
        return {"success": False, "message": f"{section} 数据格式异常"}
    if idx is None:
        return {"success": False, "message": f"未找到 id={item_id} 的条目"}

    highlights = items[idx].get("highlights") or []
    if not isinstance(highlights, list):
        return {"success": False, "message": "bullets 数据格式异常"}

    next_text = str(text or "").strip()
    for highlight in highlights:
        if str(highlight.get("id")) == str(highlight_id):
            before = snapshot(highlight)
            highlight["text"] = next_text
            section_name = SECTION_NAMES.get(section, section)
            item_label = summarize_dict(items[idx])
            diff_payload = build_diff_payload(
                title=f"{section_name} / {item_label} 修改要点",
                before=before,
                after=highlight,
                reason=normalize_reason(reason),
            )
            return {
                "success": True,
                "message": f"已更新 {section_name} 中的要点",
                "updated_section": section,
                **diff_payload,
            }
    return {"success": False, "message": f"未找到 id={highlight_id} 的要点"}


def update_bullet(
    resume_content: dict[str, Any],
    section: str,
    item_id: str,
    bullet_id: str,
    text: Any,
    reason: Any = None,
) -> dict[str, Any]:
    """用于精确更新某条 resume bullet 的文本内容。"""
    return update_highlight(
        resume_content,
        section=section,
        item_id=item_id,
        highlight_id=bullet_id,
        text=text,
        reason=reason,
    )


__all__ = ["update_bullet", "update_highlight"]
