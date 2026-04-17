"""用于把简历信息整理成面试提示词所需的上下文。"""

from __future__ import annotations

import json
from typing import Any

from app.schemas.resume import dump_resume_content_for_frontend


def build_interviewer_prompt_context(context: dict[str, Any]) -> dict[str, Any]:
    """用于生成面试 Agent 渲染系统提示词所需的变量。"""
    resume_content = dump_resume_content_for_frontend(context["resume_content"])
    job_application = resume_content.get("job_application", {})
    return {
        "target_title": str(job_application.get("target_title", "") or ""),
        "target_company": str(job_application.get("target_company", "") or ""),
        "jd_text": str(job_application.get("jd_text", "") or ""),
        "resume_json": json.dumps(resume_content, ensure_ascii=False, indent=2),
    }


__all__ = ["build_interviewer_prompt_context"]
