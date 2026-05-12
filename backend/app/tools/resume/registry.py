"""用于集中声明简历工具 schema 和分发关系。"""

from __future__ import annotations

from typing import Any

from app.tools.observability import query_logs_logql, query_metrics_promql

from .add_highlight_tool import add_bullet, add_highlight
from .read_resume_tool import read_resume_content
from .remove_highlight_tool import remove_bullet, remove_highlight
from .update_highlight_tool import update_bullet, update_highlight
from .update_overview_tool import update_overview

_BULLET_SECTIONS = ["education", "work_experience", "projects"]

RESUME_TOOLS_SCHEMA: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "update_overview",
            "description": (
                "更新 projects 板块中某个项目的 overview 简介，不修改其他事实字段。"
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
            "name": "query_logs_logql",
            "description": (
                "用 LogQL 查询本地 Loki 日志，只读。适合排查 agent trace、"
                "请求错误、工具执行失败和指定 request_id/session_id 的日志。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            'LogQL 查询，例如 {app="chat-resume",service="backend"}'
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "description": "最多返回的日志行数，默认 20。",
                    },
                    "start": {
                        "type": "string",
                        "description": "可选，Loki 支持的开始时间戳或相对时间。",
                    },
                    "end": {
                        "type": "string",
                        "description": "可选，Loki 支持的结束时间戳或相对时间。",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_metrics_promql",
            "description": (
                "用 PromQL 查询本地 Prometheus 指标，只读。适合查看请求量、"
                "延迟、错误率和数据库查询耗时。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "PromQL 查询，例如 "
                            "rate(chat_resume_http_requests_total[5m])"
                        ),
                    },
                    "time": {
                        "type": "string",
                        "description": "可选，Prometheus instant query 的时间点。",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_bullet",
            "description": "精准更新某个条目下单条 bullet 的文本。",
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
            "description": "向某个条目新增一条 bullet。",
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
            "description": "从某个条目删除一条 bullet。",
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

_RESUME_TOOL_HANDLERS = {
    "read_resume": read_resume_content,
    "update_overview": update_overview,
    "update_bullet": update_bullet,
    "add_bullet": add_bullet,
    "remove_bullet": remove_bullet,
    "update_highlight": update_highlight,
    "add_highlight": add_highlight,
    "remove_highlight": remove_highlight,
    "query_logs_logql": query_logs_logql,
    "query_metrics_promql": query_metrics_promql,
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


__all__ = ["RESUME_TOOLS_SCHEMA", "execute_resume_tool"]
