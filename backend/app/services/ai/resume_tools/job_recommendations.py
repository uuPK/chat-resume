"""
Boss直聘职位推荐工具
"""

from typing import Dict, Any

from .boss_client import fetch_jobs


def get_recommend_jobs(
    resume_content: Dict[str, Any],
    page: int = 1,
    experience: str = "不限",
    job_type: str = "全职",
    salary: str = "不限",
) -> Dict[str, Any]:
    """获取推荐职位列表"""
    result = fetch_jobs(
        {
            "page": page,
            "experience": experience,
            "jobType": job_type,
            "salary": salary,
        }
    )
    result["tool"] = "get_recommend_jobs"
    return result
