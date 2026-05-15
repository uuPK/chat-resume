"""用于把简历内容整理成提示词模板可消费的上下文。"""

from __future__ import annotations

import copy
import json
from typing import Any

from app.schemas.resume import dump_resume_content_for_frontend
from app.runtime.resume_agent_session import maybe_compact_resume_context


def strip_redundant_fields(resume_content: dict[str, Any]) -> dict[str, Any]:
    """用于移除当前提示词阶段不需要的冗余字段。"""
    content = dump_resume_content_for_frontend(copy.deepcopy(resume_content))
    for section in ("work_experience", "projects"):
        items = content.get(section)
        if isinstance(items, list):
            for item in items:
                item.pop("achievements", None)
    return content


def build_resume_prompt_context(context: dict[str, Any]) -> dict[str, Any]:
    """用于构造简历 Agent 渲染系统提示词所需的变量。"""
    resume_content = context["resume_content"]
    job_application = (
        resume_content.get("job_application", {})
        if isinstance(resume_content, dict)
        else {}
    )
    prompt_resume = maybe_compact_resume_context(
        resume_content=resume_content,
        confirmed_diff_items=context.get("confirmed_diff_items"),
        conversation_history=context.get("conversation_history"),
    )
    return {
        "target_title": str(job_application.get("target_title", "") or ""),
        "target_company": str(job_application.get("target_company", "") or ""),
        "jd_text": str(job_application.get("jd_text", "") or ""),
        "available_tools": str(context.get("available_tools", "（无）") or "（无）"),
        "resume_json": json.dumps(
            prompt_resume,
            ensure_ascii=False,
            indent=2,
        ),
    }


__all__ = ["build_resume_prompt_context", "strip_redundant_fields"]
