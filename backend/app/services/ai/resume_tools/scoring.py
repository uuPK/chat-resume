"""
简历评分模块
"""

from typing import Dict, Any


def score_resume(resume_content: Dict[str, Any], criteria: str = "comprehensive") -> Dict[str, Any]:
    """按照指定标准为简历评分"""
    has_experience = len(resume_content.get("experience", [])) > 0
    has_education = len(resume_content.get("education", [])) > 0
    has_skills = len(resume_content.get("skills", [])) > 0
    has_projects = len(resume_content.get("projects", [])) > 0

    return {
        "tool": "score_resume",
        "criteria": criteria,
        "completeness": {
            "has_experience": has_experience,
            "has_education": has_education,
            "has_skills": has_skills,
            "has_projects": has_projects,
        },
        "message": "已分析简历完整性，等待AI进行详细评分",
    }
