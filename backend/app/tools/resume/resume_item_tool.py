"""用于实现简历列表条目的新增和删除工具。"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from .shared import build_diff_payload, normalize_reason, snapshot, summarize_dict

ITEM_SECTIONS = {
    "education": "edu",
    "work_experience": "work",
    "projects": "proj",
    "skills": "skill",
    "languages": "lang",
    "custom_sections": "section",
}

ITEM_FIELD_WHITELIST = {
    "education": {"school", "major", "degree", "duration", "start_date", "end_date", "location", "gpa", "highlights"},
    "work_experience": {"company", "position", "duration", "start_date", "end_date", "is_current", "location", "employment_type", "technologies", "highlights"},
    "projects": {"name", "overview", "technologies", "role", "duration", "start_date", "end_date", "github_url", "demo_url", "links", "highlights"},
    "skills": {"category", "items"},
    "languages": {"name", "level"},
    "custom_sections": {"title", "content"},
}


def add_resume_item(
    resume_content: dict[str, Any],
    section: str,
    item: Any,
    source: Any,
    reason: Any = None,
) -> dict[str, Any]:
    """用于向简历列表板块新增一个有事实来源的条目。"""
    if section not in ITEM_SECTIONS:
        return {"success": False, "message": f"{section} 不支持新增条目"}
    if not str(source or "").strip():
        return {"success": False, "message": "新增条目必须提供用户明确事实来源"}
    if not isinstance(item, dict) or not item:
        return {"success": False, "message": "新增条目不能为空"}

    items = resume_content.get(section)
    if not isinstance(items, list):
        items = []

    next_item = _sanitize_item(section, item)
    next_item["id"] = f"{ITEM_SECTIONS[section]}_{uuid4().hex[:12]}"
    items.append(next_item)
    resume_content[section] = items

    diff_payload = build_diff_payload(
        title=f"{_section_label(section)} 新增条目",
        before="（新增）",
        after=next_item,
        reason=normalize_reason(reason),
    )
    return {
        "success": True,
        "message": f"已新增{_section_label(section)}条目",
        "updated_section": section,
        "source": str(source).strip(),
        **diff_payload,
    }


def remove_resume_item(
    resume_content: dict[str, Any],
    section: str,
    item_id: str,
    reason: Any = None,
) -> dict[str, Any]:
    """用于从简历列表板块删除一个已有条目。"""
    if section not in ITEM_SECTIONS:
        return {"success": False, "message": f"{section} 不支持删除条目"}

    items = resume_content.get(section)
    if not isinstance(items, list):
        return {"success": False, "message": f"{section} 数据格式异常"}

    idx = next((i for i, item in enumerate(items) if str(item.get("id")) == str(item_id)), None)
    if idx is None:
        return {"success": False, "message": f"未找到 id={item_id} 的条目"}

    before = snapshot(items[idx])
    del items[idx]
    resume_content[section] = items

    diff_payload = build_diff_payload(
        title=f"{_section_label(section)} 删除条目",
        before=before,
        after="（已删除）",
        reason=normalize_reason(reason),
    )
    return {
        "success": True,
        "message": f"已删除{_section_label(section)}条目",
        "updated_section": section,
        **diff_payload,
    }


def _sanitize_item(section: str, item: dict[str, Any]) -> dict[str, Any]:
    """用于按板块白名单过滤新增条目字段。"""
    allowed = ITEM_FIELD_WHITELIST[section]
    return {str(key): value for key, value in item.items() if str(key) in allowed}


def _section_label(section: str) -> str:
    """用于把简历板块 key 转成简短中文标签。"""
    labels = {
        "education": "教育经历",
        "work_experience": "工作经历",
        "projects": "项目经历",
        "skills": "技能专长",
        "languages": "语言能力",
        "custom_sections": "自定义板块",
    }
    return labels.get(section, summarize_dict({"name": section}))


__all__ = ["ITEM_FIELD_WHITELIST", "ITEM_SECTIONS", "add_resume_item", "remove_resume_item"]
