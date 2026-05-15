"""用于把简历内容整理成提示词模板可消费的上下文。"""

from __future__ import annotations

import copy
import json
from typing import Any

from app.schemas.resume import dump_resume_content_for_frontend
from app.runtime.resume_agent_session import maybe_compact_resume_context

_EDIT_TOOL_NAMES = {
    "update_overview",
    "update_bullet",
    "add_bullet",
    "remove_bullet",
}


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
    available_tool_names = _available_tool_names(context)
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
        "tool_usage_rules": _tool_usage_rules(available_tool_names),
        "tool_protocol": _tool_protocol(available_tool_names),
        "resume_json": json.dumps(
            prompt_resume,
            ensure_ascii=False,
            indent=2,
        ),
    }


def _available_tool_names(context: dict[str, Any]) -> set[str]:
    """用于从 runtime 上下文读取当前实际可用工具名。"""
    value = context.get("available_tool_names")
    if not isinstance(value, list):
        return set()
    return {str(item) for item in value if item}


def _has_edit_tools(tool_names: set[str]) -> bool:
    """用于判断当前工具集是否允许修改简历。"""
    return bool(_EDIT_TOOL_NAMES & tool_names)


def _tool_usage_rules(tool_names: set[str]) -> str:
    """用于根据当前工具集生成工具使用硬约束。"""
    lines: list[str] = []
    if _has_edit_tools(tool_names):
        lines.append(
            "- 默认执行 `optimize-first`：用户要求优化、润色、增强、改简历且有可改内容时，必须直接调用工具产出改动；首轮目标是“先产出改动”。"
        )
    else:
        lines.append("- 当前轮次只读：不要修改简历；如需工具，只调用“可用工具”中的只读工具。")
    if "generate_job_match_summary" in tool_names:
        lines.append(
            "- 当用户询问岗位匹配、关键词命中、缺失关键词、需要补充事实，或你需要展示 JD 证据链时，可调用 `generate_job_match_summary`。"
        )
    return "\n".join(lines)


def _tool_protocol(tool_names: set[str]) -> str:
    """用于根据当前工具集生成工具调用协议。"""
    lines: list[str] = []
    if _has_edit_tools(tool_names):
        lines.extend(
            [
                "- 改单条要点用 `update_bullet(section,item_id,bullet_id,text,reason)`；新增要点用 `add_bullet(section,item_id,text,reason)`；删除要点用 `remove_bullet(section,item_id,bullet_id,reason)`。",
                "- 改项目简介只用 `update_overview(section,item_id,overview,reason)`，其中 section 必须是 `projects`。",
                "- section 只能是 `education`、`work_experience`、`projects`；item_id / bullet_id 必须来自当前简历 JSON。",
                "- 首轮优先改已有 bullet；只有已有 bullet 无法承载岗位关键词时才新增 bullet。",
            ]
        )
    if "generate_job_match_summary" in tool_names:
        lines.append("- 生成岗位匹配、关键词命中或证据链摘要时，调用 `generate_job_match_summary`。")
    return "\n".join(lines) if lines else "（无）"


__all__ = ["build_resume_prompt_context", "strip_redundant_fields"]
