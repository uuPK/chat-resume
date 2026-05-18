"""用于集中声明简历工具 schema 和分发关系。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .add_highlight_tool import add_bullet, add_highlight
from .job_match_summary_tool import generate_job_match_summary
from .read_resume_tool import read_resume_content
from .remove_highlight_tool import remove_bullet, remove_highlight
from .resume_item_tool import add_resume_item, remove_resume_item
from .update_highlight_tool import update_bullet, update_highlight
from .update_item_fields_tool import update_item_fields
from .update_overview_tool import update_overview
from .update_profile_tool import update_profile
from .update_skills_tool import update_skills
from .update_summary_tool import update_summary

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
            "name": "remove_resume_item",
            "description": (
                "删除简历列表板块中的一个已有条目。section 只能是 education、"
                "work_experience、projects、skills、languages、custom_sections；"
                "item_id 必须来自当前简历 JSON。仅在用户明确要删除或该条目明显"
                "不适合目标岗位时使用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "section": {
                        "type": "string",
                        "enum": [
                            "education",
                            "work_experience",
                            "projects",
                            "skills",
                            "languages",
                            "custom_sections",
                        ],
                    },
                    "item_id": {
                        "type": "string",
                        "description": "要删除的条目 id",
                    },
                    "reason": {
                        "type": "string",
                        "description": "本次删除的简短理由，供前端展示",
                    },
                },
                "required": ["section", "item_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_resume_item",
            "description": (
                "向简历列表板块新增一段工作、项目、教育、技能、语言或自定义内容。"
                "section 只能是 education、work_experience、projects、skills、"
                "languages、custom_sections。必须提供 source 表示用户明确事实来源；"
                "不能编造项目、公司、学历、技能或年限。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "section": {
                        "type": "string",
                        "enum": [
                            "education",
                            "work_experience",
                            "projects",
                            "skills",
                            "languages",
                            "custom_sections",
                        ],
                    },
                    "item": {
                        "type": "object",
                        "description": "新增条目的字段对象",
                    },
                    "source": {
                        "type": "string",
                        "description": "用户明确提供该事实的来源说明",
                    },
                    "reason": {
                        "type": "string",
                        "description": "本次新增的简短理由，供前端展示",
                    },
                },
                "required": ["section", "item", "source"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_skills",
            "description": (
                "更新技能板块中某个技能分类的名称和技能列表。category_id 必须来自"
                "当前简历 JSON；mode 为 replace 或 merge。只能补充或调整简历中"
                "已有证据或用户明确提供的技能，不得编造能力。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "category_id": {
                        "type": "string",
                        "description": "技能分类条目的 id",
                    },
                    "category": {
                        "type": "string",
                        "description": "新的技能分类名称",
                    },
                    "items": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "技能列表",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["replace", "merge"],
                        "description": "replace 替换列表，merge 合并追加",
                    },
                    "reason": {
                        "type": "string",
                        "description": "本次修改的简短理由，供前端展示",
                    },
                },
                "required": ["category_id", "items"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_item_fields",
            "description": (
                "更新工作、项目或教育条目的非 bullet 字段。section 只能是 "
                "education、work_experience、projects；item_id 必须来自当前简历 JSON。"
                "只修改 fields 中给出的白名单字段，不新增事实。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "section": {"type": "string", "enum": _BULLET_SECTIONS},
                    "item_id": {
                        "type": "string",
                        "description": "工作/项目/教育条目的 id",
                    },
                    "fields": {
                        "type": "object",
                        "description": (
                            "要更新的字段。education 支持 school/major/degree/duration/"
                            "start_date/end_date/location/gpa；work_experience 支持 "
                            "company/position/duration/start_date/end_date/is_current/"
                            "location/employment_type/technologies；projects 支持 "
                            "name/overview/technologies/role/duration/start_date/end_date/"
                            "github_url/demo_url/links。"
                        ),
                    },
                    "reason": {
                        "type": "string",
                        "description": "本次修改的简短理由，供前端展示",
                    },
                },
                "required": ["section", "item_id", "fields"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_profile",
            "description": (
                "更新个人信息 personal_info 中可安全优化的字段。仅支持 "
                "position、headline、location、github、linkedin、website、links；"
                "不得修改 name、email、phone。适合调整求职定位、标题和公开链接。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "fields": {
                        "type": "object",
                        "description": "要更新的个人信息字段和值",
                        "properties": {
                            "position": {"type": "string"},
                            "headline": {"type": "string"},
                            "location": {"type": "string"},
                            "github": {"type": "string"},
                            "linkedin": {"type": "string"},
                            "website": {"type": "string"},
                            "links": {
                                "type": "array",
                                "items": {"type": "object"},
                            },
                        },
                        "additionalProperties": False,
                    },
                    "reason": {
                        "type": "string",
                        "description": "本次修改的简短理由，供前端展示",
                    },
                },
                "required": ["fields"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_summary",
            "description": (
                "更新个人总结 summary.text。适合把整份简历的职业定位、"
                "核心能力摘要改成更贴合目标岗位和 JD 的版本。不得编造经历、"
                "数字、年限或结果。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "新的个人总结文本",
                    },
                    "reason": {
                        "type": "string",
                        "description": "本次修改的简短理由，供前端展示",
                    },
                },
                "required": ["text"],
            },
        },
    },
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
        "update_summary",
        update_summary,
        _SCHEMA_BY_NAME.get("update_summary"),
    ),
    ResumeToolDefinition(
        "update_profile",
        update_profile,
        _SCHEMA_BY_NAME.get("update_profile"),
    ),
    ResumeToolDefinition(
        "update_item_fields",
        update_item_fields,
        _SCHEMA_BY_NAME.get("update_item_fields"),
    ),
    ResumeToolDefinition(
        "update_skills",
        update_skills,
        _SCHEMA_BY_NAME.get("update_skills"),
    ),
    ResumeToolDefinition(
        "add_resume_item",
        add_resume_item,
        _SCHEMA_BY_NAME.get("add_resume_item"),
    ),
    ResumeToolDefinition(
        "remove_resume_item",
        remove_resume_item,
        _SCHEMA_BY_NAME.get("remove_resume_item"),
    ),
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
