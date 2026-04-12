"""
编辑简历内容工具
"""

from typing import Dict, Any, List
from copy import deepcopy
from uuid import uuid4
import json

_SECTION_NAMES = {
    "education": "教育经历",
    "work_experience": "工作经历",
    "projects": "项目经历",
}

_HIGHLIGHT_SECTIONS = {"education", "work_experience", "projects"}


def _summarize_value(value: Any, max_length: int = 160) -> str:
    """将任意值压缩成适合展示的短文本。"""
    if value in (None, "", [], {}):
      return "空"

    if isinstance(value, str):
        return _truncate(value.replace("\n", " "), max_length)

    if isinstance(value, list):
        if not value:
            return "空"
        items = []
        for item in value[:3]:
            if isinstance(item, dict):
                items.append(_summarize_dict(item))
            else:
                items.append(_truncate(str(item), 40))
        suffix = "" if len(value) <= 3 else f" 等共 {len(value)} 项"
        return _truncate("；".join(items) + suffix, max_length)

    if isinstance(value, dict):
        return _truncate(_summarize_dict(value), max_length)

    return _truncate(str(value), max_length)


def _summarize_dict(data: Dict[str, Any]) -> str:
    """提取字典中适合阅读的关键字段。"""
    preferred_keys = [
        "name",
        "title",
        "company",
        "school",
        "position",
        "role",
        "degree",
        "major",
        "duration",
        "description",
        "text",
    ]
    values = []
    for key in preferred_keys:
        raw = data.get(key)
        if raw:
            values.append(str(raw).replace("\n", " "))
    if not values:
        try:
            return json.dumps(data, ensure_ascii=False)
        except TypeError:
            return str(data)
    return " | ".join(values[:4])


def _truncate(text: str, max_length: int) -> str:
    """截断长文本。"""
    if len(text) <= max_length:
        return text
    return text[: max_length - 1] + "…"


def _find_item(
    resume_content: Dict[str, Any], section: str, item_id: str
) -> tuple[List[Dict[str, Any]], int] | tuple[None, None]:
    items: List[Dict[str, Any]] = resume_content.get(section) or []
    if not isinstance(items, list):
        return None, None
    idx = next(
        (i for i, item in enumerate(items) if str(item.get("id")) == str(item_id)),
        None,
    )
    if idx is None:
        return items, None
    return items, idx


def update_overview(
    resume_content: Dict[str, Any], section: str, item_id: str, overview: Any
) -> Dict[str, Any]:
    """更新项目条目的 overview 字段。"""
    if section != "projects":
        return {"success": False, "message": "只有 projects 支持 overview 编辑"}

    items, idx = _find_item(resume_content, section, item_id)
    if items is None:
        return {"success": False, "message": f"{section} 数据格式异常"}
    if idx is None:
        return {"success": False, "message": f"未找到 id={item_id} 的条目"}

    next_overview = str(overview or "").strip()
    before = deepcopy(items[idx])
    items[idx]["overview"] = next_overview
    resume_content[section] = items

    section_name = _SECTION_NAMES.get(section, section)
    item_label = _summarize_dict(items[idx])
    diff = (
        f"{section_name} / {item_label} 修改摘要\n"
        f"  改前：{_summarize_value(before.get('overview'))}\n"
        f"  改后：{_summarize_value(next_overview)}"
    )
    return {
        "success": True,
        "message": f"已更新 {section_name} 的简介",
        "updated_section": section,
        "diff_summary": diff,
    }


def update_highlight(
    resume_content: Dict[str, Any],
    section: str,
    item_id: str,
    highlight_id: str,
    text: Any,
) -> Dict[str, Any]:
    """更新某条 highlight 的文本。"""
    if section not in _HIGHLIGHT_SECTIONS:
        return {"success": False, "message": f"{section} 不支持亮点编辑"}

    items, idx = _find_item(resume_content, section, item_id)
    if items is None:
        return {"success": False, "message": f"{section} 数据格式异常"}
    if idx is None:
        return {"success": False, "message": f"未找到 id={item_id} 的条目"}

    highlights = items[idx].get("highlights") or []
    if not isinstance(highlights, list):
        return {"success": False, "message": "highlights 数据格式异常"}

    next_text = str(text or "").strip()
    for highlight in highlights:
        if str(highlight.get("id")) == str(highlight_id):
            before = deepcopy(highlight)
            highlight["text"] = next_text
            section_name = _SECTION_NAMES.get(section, section)
            item_label = _summarize_dict(items[idx])
            return {
                "success": True,
                "message": f"已更新 {section_name} 中的亮点",
                "updated_section": section,
                "diff_summary": (
                    f"{section_name} / {item_label} 修改摘要\n"
                    f"  改前：{_summarize_value(before)}\n"
                    f"  改后：{_summarize_value(highlight)}"
                ),
            }
    return {"success": False, "message": f"未找到 id={highlight_id} 的亮点"}


def add_highlight(
    resume_content: Dict[str, Any], section: str, item_id: str, text: Any
) -> Dict[str, Any]:
    """向某个条目新增一条 highlight。"""
    if section not in _HIGHLIGHT_SECTIONS:
        return {"success": False, "message": f"{section} 不支持亮点编辑"}

    items, idx = _find_item(resume_content, section, item_id)
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

    section_name = _SECTION_NAMES.get(section, section)
    item_label = _summarize_dict(items[idx])
    return {
        "success": True,
        "message": f"已在 {section_name} 中新增亮点",
        "updated_section": section,
        "diff_summary": (
            f"{section_name} / {item_label} 新增亮点\n"
            f"  改前：（新增）\n"
            f"  改后：{_summarize_value(highlight)}"
        ),
    }


def remove_highlight(
    resume_content: Dict[str, Any], section: str, item_id: str, highlight_id: str
) -> Dict[str, Any]:
    """从某个条目删除一条 highlight。"""
    if section not in _HIGHLIGHT_SECTIONS:
        return {"success": False, "message": f"{section} 不支持亮点编辑"}

    items, idx = _find_item(resume_content, section, item_id)
    if items is None:
        return {"success": False, "message": f"{section} 数据格式异常"}
    if idx is None:
        return {"success": False, "message": f"未找到 id={item_id} 的条目"}

    highlights = items[idx].get("highlights") or []
    if not isinstance(highlights, list):
        return {"success": False, "message": "highlights 数据格式异常"}

    remaining = [
        highlight for highlight in highlights if str(highlight.get("id")) != str(highlight_id)
    ]
    if len(remaining) == len(highlights):
        return {"success": False, "message": f"未找到 id={highlight_id} 的亮点"}

    removed = next(
        highlight for highlight in highlights if str(highlight.get("id")) == str(highlight_id)
    )
    items[idx]["highlights"] = remaining
    resume_content[section] = items

    section_name = _SECTION_NAMES.get(section, section)
    item_label = _summarize_dict(items[idx])
    return {
        "success": True,
        "message": f"已从 {section_name} 中删除亮点",
        "updated_section": section,
        "diff_summary": (
            f"{section_name} / {item_label} 删除亮点\n"
            f"  改前：{_summarize_value(removed)}\n"
            f"  改后：（已删除）"
        ),
    }
