"""用于把岗位匹配摘要暴露为简历 Agent 只读工具。"""

from __future__ import annotations

from typing import Any


def generate_job_match_summary(
    resume_content: dict[str, Any],
    confirmed_diff_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """用于基于当前简历和本轮已确认改动生成岗位匹配摘要。"""
    from app.services.agent.job_match_summary import build_job_match_summary

    summary = build_job_match_summary(
        original_resume=resume_content,
        latest_resume_content=resume_content,
        confirmed_diff_items=confirmed_diff_items or [],
    )
    if summary is None:
        return {
            "success": False,
            "message": "缺少 JD 或可解释的匹配证据，暂不生成岗位匹配摘要。",
        }
    return {
        "success": True,
        "message": "已生成岗位匹配摘要。",
        "job_match_summary": summary,
    }


__all__ = ["generate_job_match_summary"]
