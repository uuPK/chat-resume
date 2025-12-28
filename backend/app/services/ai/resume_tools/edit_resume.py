"""
编辑简历内容工具
"""

from typing import Dict, Any
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

    # 更新简历内容
    resume_content[section] = parsed_data

    return {
        "success": True,
        "message": f"已成功更新{section_names[section]}",
        "updated_section": section,
    }
