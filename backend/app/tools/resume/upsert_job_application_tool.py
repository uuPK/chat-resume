"""用于创建或更新简历求职目标上下文。"""

from __future__ import annotations

from typing import Any

from .shared import build_diff_payload, normalize_reason, snapshot

_MISSING = object()
JOB_APPLICATION_FIELDS = {"target_company", "target_title", "jd_text"}


def upsert_job_application(
    resume_content: dict[str, Any],
    target_company: Any = _MISSING,
    target_title: Any = _MISSING,
    jd_text: Any = _MISSING,
    reason: Any = None,
) -> dict[str, Any]:
    """用于维护当前简历唯一的目标公司、目标岗位和 JD 文本。"""
    fields = _provided_fields(
        target_company=target_company,
        target_title=target_title,
        jd_text=jd_text,
    )
    if not fields:
        return {"success": False, "message": "求职目标更新字段不能为空"}

    job_application = resume_content.get("job_application")
    if not isinstance(job_application, dict):
        job_application = {}

    before = snapshot(job_application)
    job_application.update(fields)
    resume_content["job_application"] = job_application

    diff_payload = build_diff_payload(
        title="求职目标 修改内容",
        before={key: before.get(key) for key in fields},
        after={key: job_application.get(key) for key in fields},
        reason=normalize_reason(reason),
    )
    return {
        "success": True,
        "message": "已更新求职目标",
        "updated_section": "job_application",
        **diff_payload,
    }


def _provided_fields(**values: Any) -> dict[str, str]:
    """用于只保留调用方明确传入的求职目标字段。"""
    return {
        key: str(value or "").strip()
        for key, value in values.items()
        if value is not _MISSING
    }


__all__ = ["JOB_APPLICATION_FIELDS", "upsert_job_application"]
