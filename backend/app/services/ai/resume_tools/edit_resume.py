"""
编辑简历内容工具
"""

from typing import Dict, Any
from copy import deepcopy
import json


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
