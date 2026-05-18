"""用于创建或更新简历求职目标上下文。"""

from __future__ import annotations

from typing import Any

from .shared import normalize_reason, snapshot, summarize_value

_MISSING = object()
JOB_APPLICATION_FIELDS = {"target_company", "target_title", "jd_text"}


def upsert_job_application(
    resume_content: dict[str, Any],
    fields: Any = None,
    reason: Any = None,
    target_company: Any = _MISSING,
    target_title: Any = _MISSING,
    jd_text: Any = _MISSING,
) -> dict[str, Any]:
    """用于维护当前简历唯一的目标公司、目标岗位和 JD 文本。"""
    field_result = _provided_fields(
        fields,
        target_company=target_company,
        target_title=target_title,
        jd_text=jd_text,
    )
    if isinstance(field_result, str):
        return {"success": False, "message": field_result}
    if not field_result:
        return {"success": False, "message": "求职目标更新字段不能为空"}

    job_application = resume_content.get("job_application")
    if not isinstance(job_application, dict):
        job_application = {}

    before = snapshot(job_application)
    changed_fields = _changed_fields(before=before, fields=field_result)
    if not changed_fields:
        return {
            "success": True,
            "message": "求职目标没有实际变化",
            "updated_section": "job_application",
            "diff_summary": "求职目标没有实际变化",
            "diff_items": [],
        }

    job_application.update(changed_fields)
    resume_content["job_application"] = job_application

    diff_payload = _build_job_application_diff(
        before=before,
        after=job_application,
        fields=changed_fields,
        reason=normalize_reason(reason),
    )
    return {
        "success": True,
        "message": "已更新求职目标",
        "updated_section": "job_application",
        **diff_payload,
    }


def _provided_fields(fields: Any, **legacy_values: Any) -> dict[str, str] | str:
    """用于只保留调用方明确传入的求职目标字段。"""
    if fields is not None:
        return _fields_from_payload(fields)
    return {
        key: str(value or "").strip()
        for key, value in legacy_values.items()
        if value is not _MISSING
    }


def _fields_from_payload(fields: Any) -> dict[str, str] | str:
    """用于校验fields载荷并提取允许修改的求职目标字段。"""
    if not isinstance(fields, dict):
        return "求职目标 fields 必须是对象"
    invalid_fields = sorted(set(str(key) for key in fields) - JOB_APPLICATION_FIELDS)
    if invalid_fields:
        return f"upsert_job_application 不支持修改字段: {', '.join(invalid_fields)}"
    return {
        str(key): str(value or "").strip()
        for key, value in fields.items()
    }


def _changed_fields(*, before: dict[str, Any], fields: dict[str, str]) -> dict[str, str]:
    """用于过滤求职目标里没有实际变化的字段。"""
    return {
        key: value
        for key, value in fields.items()
        if str(before.get(key) or "").strip() != value
    }


def _build_job_application_diff(
    *,
    before: dict[str, Any],
    after: dict[str, Any],
    fields: dict[str, str],
    reason: str,
) -> dict[str, Any]:
    """用于生成只展示被修改值的求职目标 diff。"""
    diff_items = [
        {
            "before": summarize_value(before.get(key)),
            "after": summarize_value(after.get(key)),
            "reason": reason,
        }
        for key in fields
    ]
    lines = ["求职目标 修改内容"]
    for item in diff_items:
        lines.append(f"  改前：{item['before']}")
        lines.append(f"  改后：{item['after']}")
        if item["reason"]:
            lines.append(f"  改动理由：{item['reason']}")
    return {"diff_summary": "\n".join(lines), "diff_items": diff_items}


__all__ = ["JOB_APPLICATION_FIELDS", "upsert_job_application"]
