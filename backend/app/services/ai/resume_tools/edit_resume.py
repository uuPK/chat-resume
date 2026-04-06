"""
编辑简历内容工具
"""

from typing import Dict, Any, List
from copy import deepcopy
from uuid import uuid4
import json

# 支持数组的板块
_LIST_SECTIONS = {"education", "work_experience", "skills", "projects", "languages"}

_SECTION_NAMES = {
    "personal_info": "个人信息",
    "education": "教育经历",
    "work_experience": "工作经历",
    "skills": "技能",
    "projects": "项目经历",
    "summary": "个人总结",
    "languages": "语言能力",
}


def _stable_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


_ID_PREFIX = {
    "education": "edu",
    "work_experience": "work",
    "skills": "skill",
    "projects": "proj",
    "languages": "lang",
}


def edit_resume_content(
    resume_content: Dict[str, Any], section: str, data: Any
) -> Dict[str, Any]:
    """
    编辑简历特定板块内容

    Args:
        resume_content: 简历内容字典（会被原地修改）
        section: 要修改的板块名称
        data: 新数据（可以是字符串或结构化数据）

    Returns:
        Dict[str, Any]: 操作结果
    """
    # 板块名称映射和描述
    section_names = {
        "personal_info": "个人信息",
        "education": "教育经历",
        "work_experience": "工作经历",
        "skills": "技能",
        "projects": "项目经历",
        "summary": "个人总结",
        "languages": "语言能力",
    }

    if section not in section_names:
        return {"success": False, "message": f"未知的板块: {section}"}

    # 解析 data（如果是 JSON 字符串则转为对象）
    parsed_data = data
    if isinstance(data, str):
        try:
            parsed_data = json.loads(data)
        except json.JSONDecodeError:
            # 非 JSON 字符串，保持原样（如 summary 是纯文本）
            parsed_data = data

    old_data = deepcopy(resume_content.get(section))

    # 更新简历内容
    resume_content[section] = parsed_data
    diff_summary = _build_diff_summary(
        section_name=section_names[section],
        before=old_data,
        after=parsed_data,
    )

    return {
        "success": True,
        "message": f"已成功更新{section_names[section]}",
        "updated_section": section,
        "diff_summary": diff_summary,
    }


def _build_diff_summary(section_name: str, before: Any, after: Any) -> str:
    """构建可读 diff 摘要。"""
    before_text = _summarize_value(before)
    after_text = _summarize_value(after)
    return (
        f"{section_name}修改摘要\n"
        f"改前：{before_text}\n"
        f"改后：{after_text}"
    )


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


# ---------------------------------------------------------------------------
# 精细化编辑工具
# ---------------------------------------------------------------------------

def update_resume_item(
    resume_content: Dict[str, Any], section: str, item_id: str, patch: Any
) -> Dict[str, Any]:
    """更新数组板块中某个条目的部分字段。"""
    if section not in _LIST_SECTIONS:
        return {"success": False, "message": f"{section} 不支持条目级编辑"}

    items: List[Dict[str, Any]] = resume_content.get(section) or []
    if not isinstance(items, list):
        return {"success": False, "message": f"{section} 数据格式异常"}

    # 解析 patch
    if isinstance(patch, str):
        try:
            patch = json.loads(patch)
        except json.JSONDecodeError as e:
            return {"success": False, "message": f"patch 解析失败: {e}"}

    if not isinstance(patch, dict):
        return {"success": False, "message": "patch 必须是对象"}

    idx = next((i for i, item in enumerate(items) if str(item.get("id")) == str(item_id)), None)
    if idx is None:
        return {"success": False, "message": f"未找到 id={item_id} 的条目"}

    before = deepcopy(items[idx])
    items[idx] = {**items[idx], **patch}
    resume_content[section] = items

    section_name = _SECTION_NAMES.get(section, section)
    item_label = _summarize_dict(items[idx])

    # 字段级 diff：只显示 patch 中实际变动的字段
    lines = []
    for key, new_val in patch.items():
        old_val = before.get(key)
        if old_val != new_val:
            lines.append(
                f"{key}:\n  改前：{_summarize_value(old_val)}\n  改后：{_summarize_value(new_val)}"
            )
    diff = (
        f"{section_name} / {item_label} 修改摘要\n"
        + ("\n".join(lines) if lines else "无字段变动")
    )

    return {
        "success": True,
        "message": f"已更新 {section_name} 中的条目",
        "updated_section": section,
        "diff_summary": diff,
    }


def add_resume_item(
    resume_content: Dict[str, Any], section: str, item: Any
) -> Dict[str, Any]:
    """向数组板块末尾追加一个新条目。"""
    if section not in _LIST_SECTIONS:
        return {"success": False, "message": f"{section} 不支持条目追加"}

    if isinstance(item, str):
        try:
            item = json.loads(item)
        except json.JSONDecodeError as e:
            return {"success": False, "message": f"item 解析失败: {e}"}

    if not isinstance(item, dict):
        return {"success": False, "message": "item 必须是对象"}

    # 保证有稳定 id
    if not item.get("id"):
        item = {"id": _stable_id(_ID_PREFIX.get(section, "item")), **item}

    items: List[Dict[str, Any]] = resume_content.get(section) or []
    if not isinstance(items, list):
        items = []
    items.append(item)
    resume_content[section] = items

    section_name = _SECTION_NAMES.get(section, section)
    return {
        "success": True,
        "message": f"已在 {section_name} 中新增条目",
        "updated_section": section,
        "diff_summary": f"{section_name} 新增：{_summarize_dict(item)}",
    }


def remove_resume_item(
    resume_content: Dict[str, Any], section: str, item_id: str
) -> Dict[str, Any]:
    """从数组板块中删除指定 id 的条目。"""
    if section not in _LIST_SECTIONS:
        return {"success": False, "message": f"{section} 不支持条目删除"}

    items: List[Dict[str, Any]] = resume_content.get(section) or []
    if not isinstance(items, list):
        return {"success": False, "message": f"{section} 数据格式异常"}

    new_items = [item for item in items if str(item.get("id")) != str(item_id)]
    if len(new_items) == len(items):
        return {"success": False, "message": f"未找到 id={item_id} 的条目"}

    removed = next(item for item in items if str(item.get("id")) == str(item_id))
    resume_content[section] = new_items

    section_name = _SECTION_NAMES.get(section, section)
    return {
        "success": True,
        "message": f"已从 {section_name} 中删除条目",
        "updated_section": section,
        "diff_summary": f"{section_name} 删除：{_summarize_dict(removed)}",
    }
