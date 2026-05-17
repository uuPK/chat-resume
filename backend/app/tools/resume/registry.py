"""用于集中声明简历工具 schema 和分发关系。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .add_highlight_tool import add_bullet, add_highlight
from .job_match_summary_tool import generate_job_match_summary
from .read_resume_tool import read_resume_content
from .remove_highlight_tool import remove_bullet, remove_highlight
from .update_highlight_tool import update_bullet, update_highlight
from .update_overview_tool import update_overview

_BULLET_SECTIONS = ["education", "work_experience", "projects"]


@dataclass(frozen=True)
class ResumeToolDefinition:
    """用于把工具 schema、handler 和分类收敛成一个定义单元。"""

    name: str
    handler: Callable[..., dict[str, Any]]
    schema: dict[str, Any] | None = None
    category: str = "resume"


_RESUME_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "update_overview",
            "description": (
                "更新 projects 板块中某个项目的 overview 简介，不修改其他事实字段。"
                "仅用于项目简介，section 必须是 projects；item_id 必须来自当前简历 JSON。"
                "适合把项目简介改成更贴合岗位职责、关键词和结果表达的版本。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "section": {
                        "type": "string",
                        "enum": ["projects"],
                    },
                    "item_id": {
                        "type": "string",
                        "description": "项目条目的 id",
                    },
                    "overview": {
                        "type": "string",
                        "description": "新的项目简介文本",
                    },
                    "reason": {
                        "type": "string",
                        "description": (
                            "本次修改的简短理由，供前端展示，如“突出量化结果”"
                        ),
                    },
                },
                "required": ["section", "item_id", "overview"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_job_match_summary",
            "description": (
                "生成岗位匹配摘要，只读。适合在用户询问 JD 匹配、关键词命中、"
                "缺失关键词、需要补充哪些事实，或需要展示 JD 证据链时调用。"
                "该工具不修改简历。"
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_bullet",
            "description": (
                "精准更新某个条目下单条 bullet 的文本。用于改写已有 bullet，"
                "section 只能是 education、work_experience、projects；"
                "item_id 和 bullet_id 必须来自当前简历 JSON。适合在原 bullet "
                "已能承载岗位关键词或结果表达时使用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "section": {
                        "type": "string",
                        "enum": _BULLET_SECTIONS,
                    },
                    "item_id": {
                        "type": "string",
                        "description": "经历/项目/教育条目的 id",
                    },
                    "bullet_id": {
                        "type": "string",
                        "description": "要修改的 bullet id",
                    },
                    "text": {
                        "type": "string",
                        "description": "新的 bullet 文本",
                    },
                    "reason": {
                        "type": "string",
                        "description": (
                            "本次修改的简短理由，供前端展示，如“补充岗位关键词”"
                        ),
                    },
                },
                "required": ["section", "item_id", "bullet_id", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_bullet",
            "description": (
                "向某个条目新增一条 bullet。section 只能是 education、"
                "work_experience、projects；item_id 必须来自当前简历 JSON。"
                "仅在已有 bullet 无法承载用户目标或 JD 关键词时使用，不要编造事实。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "section": {
                        "type": "string",
                        "enum": _BULLET_SECTIONS,
                    },
                    "item_id": {
                        "type": "string",
                        "description": "经历/项目/教育条目的 id",
                    },
                    "text": {
                        "type": "string",
                        "description": "新增的 bullet 文本",
                    },
                    "reason": {
                        "type": "string",
                        "description": "本次新增的简短理由，供前端展示",
                    },
                },
                "required": ["section", "item_id", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_bullet",
            "description": (
                "从某个条目删除一条 bullet。section 只能是 education、"
                "work_experience、projects；item_id 和 bullet_id 必须来自当前简历 JSON。"
                "仅在用户明确要删除或该 bullet 与目标明显冲突时使用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "section": {
                        "type": "string",
                        "enum": _BULLET_SECTIONS,
                    },
                    "item_id": {
                        "type": "string",
                        "description": "经历/项目/教育条目的 id",
                    },
                    "bullet_id": {
                        "type": "string",
                        "description": "要删除的 bullet id",
                    },
                    "reason": {
                        "type": "string",
                        "description": "本次删除的简短理由，供前端展示",
                    },
                },
                "required": ["section", "item_id", "bullet_id"],
            },
        },
    },
]


def _schema_tool_name(schema: dict[str, Any]) -> str:
    """用于从 OpenAI function schema 中读取工具名。"""
    function = schema.get("function")
    if not isinstance(function, dict):
        return ""
    name = function.get("name")
    return name if isinstance(name, str) else ""


_SCHEMA_BY_NAME = {
    name: schema
    for schema in _RESUME_TOOL_SCHEMAS
    if (name := _schema_tool_name(schema))
}

RESUME_TOOL_CATALOG: tuple[ResumeToolDefinition, ...] = (
    ResumeToolDefinition("read_resume", read_resume_content),
    ResumeToolDefinition(
        "update_overview",
        update_overview,
        _SCHEMA_BY_NAME.get("update_overview"),
    ),
    ResumeToolDefinition(
        "update_bullet",
        update_bullet,
        _SCHEMA_BY_NAME.get("update_bullet"),
    ),
    ResumeToolDefinition("add_bullet", add_bullet, _SCHEMA_BY_NAME.get("add_bullet")),
    ResumeToolDefinition(
        "remove_bullet",
        remove_bullet,
        _SCHEMA_BY_NAME.get("remove_bullet"),
    ),
    ResumeToolDefinition(
        "generate_job_match_summary",
        generate_job_match_summary,
        _SCHEMA_BY_NAME.get("generate_job_match_summary"),
    ),
    ResumeToolDefinition("update_highlight", update_highlight),
    ResumeToolDefinition("add_highlight", add_highlight),
    ResumeToolDefinition("remove_highlight", remove_highlight),
)

RESUME_TOOLS_SCHEMA: list[dict[str, Any]] = [
    definition.schema
    for definition in RESUME_TOOL_CATALOG
    if definition.schema is not None
]
_RESUME_TOOL_HANDLERS = {
    definition.name: definition.handler for definition in RESUME_TOOL_CATALOG
}


def execute_resume_tool(
    tool_name: str,
    *,
    resume_content: dict[str, Any],
    **kwargs: Any,
) -> dict[str, Any]:
    """用于按工具名分发到对应的简历工具实现。"""
    handler = _RESUME_TOOL_HANDLERS.get(tool_name)
    if handler is None:
        return {"error": f"Unknown tool: {tool_name}"}
    return handler(resume_content, **kwargs)


__all__ = [
    "RESUME_TOOL_CATALOG",
    "RESUME_TOOLS_SCHEMA",
    "ResumeToolDefinition",
    "execute_resume_tool",
]
