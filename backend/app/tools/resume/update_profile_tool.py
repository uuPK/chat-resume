"""用于实现个人信息安全字段更新工具。"""

from __future__ import annotations

from typing import Any

from .shared import build_diff_payload, normalize_reason, snapshot

ALLOWED_PROFILE_FIELDS = {
    "position",
    "headline",
    "location",
    "github",
    "linkedin",
    "website",
    "links",
}

SOURCED_PROFILE_FIELDS = ALLOWED_PROFILE_FIELDS | {
    "name",
    "email",
    "phone",
    "address",
}


def update_profile(
    resume_content: dict[str, Any],
    fields: Any,
    source: Any = None,
    reason: Any = None,
) -> dict[str, Any]:
    """用于更新个人信息中可由 Agent 安全优化的字段。"""
    if not isinstance(fields, dict) or not fields:
        return {"success": False, "message": "个人信息更新字段不能为空"}

    source_text = str(source or "").strip()
    allowed_fields = SOURCED_PROFILE_FIELDS if source_text else ALLOWED_PROFILE_FIELDS
    invalid_fields = sorted(set(str(key) for key in fields) - allowed_fields)
    if invalid_fields:
        return {
            "success": False,
            "message": f"update_profile 不支持修改字段: {', '.join(invalid_fields)}",
        }

    profile = resume_content.get("personal_info")
    if not isinstance(profile, dict):
        profile = {}

    before = snapshot(profile)
    for key, value in fields.items():
        profile[str(key)] = _normalize_profile_value(value)
    resume_content["personal_info"] = profile

    diff_payload = build_diff_payload(
        title="个人信息 修改内容",
        before={key: before.get(key) for key in fields},
        after={key: profile.get(key) for key in fields},
        reason=normalize_reason(reason),
    )
    return {
        "success": True,
        "message": "已更新个人信息",
        "updated_section": "personal_info",
        **({"source": source_text} if source_text else {}),
        **diff_payload,
    }


def _normalize_profile_value(value: Any) -> Any:
    """用于保留 links 结构并清理普通文本字段。"""
    if isinstance(value, list):
        return value
    return str(value or "").strip()


__all__ = ["ALLOWED_PROFILE_FIELDS", "SOURCED_PROFILE_FIELDS", "update_profile"]
