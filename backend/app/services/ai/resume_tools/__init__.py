"""
简历优化工具集合
"""

from typing import Dict, Any, List

from .read_resume import read_resume_content
from .edit_resume import (
    update_overview,
    update_highlight,
    add_highlight,
    remove_highlight,
)

_HIGHLIGHT_SECTIONS = ["education", "work_experience", "projects"]


class ResumeTools:
    """提供AI可调用的工具集合"""

    @staticmethod
    def read_resume(resume_content: Dict[str, Any]) -> Dict[str, Any]:
        return read_resume_content(resume_content)

    @staticmethod
    def update_overview(
        resume_content: Dict[str, Any], section: str, item_id: str, overview: str
    ) -> Dict[str, Any]:
        return update_overview(resume_content, section, item_id, overview)

    @staticmethod
    def update_highlight(
        resume_content: Dict[str, Any],
        section: str,
        item_id: str,
        highlight_id: str,
        text: str,
    ) -> Dict[str, Any]:
        return update_highlight(resume_content, section, item_id, highlight_id, text)

    @staticmethod
    def add_highlight(
        resume_content: Dict[str, Any], section: str, item_id: str, text: str
    ) -> Dict[str, Any]:
        return add_highlight(resume_content, section, item_id, text)

    @staticmethod
    def remove_highlight(
        resume_content: Dict[str, Any], section: str, item_id: str, highlight_id: str
    ) -> Dict[str, Any]:
        return remove_highlight(resume_content, section, item_id, highlight_id)

    @classmethod
    def get_tools_schema(cls) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "update_overview",
                    "description": "更新 projects 板块中某个项目的 overview 简介，不修改其他事实字段。",
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
                        },
                        "required": ["section", "item_id", "overview"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "update_highlight",
                    "description": "精准更新某个条目下单条 highlight 的文本。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "section": {
                                "type": "string",
                                "enum": _HIGHLIGHT_SECTIONS,
                            },
                            "item_id": {
                                "type": "string",
                                "description": "经历/项目/教育条目的 id",
                            },
                            "highlight_id": {
                                "type": "string",
                                "description": "要修改的亮点 id",
                            },
                            "text": {
                                "type": "string",
                                "description": "新的亮点文本",
                            },
                        },
                        "required": ["section", "item_id", "highlight_id", "text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "add_highlight",
                    "description": "向某个条目新增一条 highlight。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "section": {
                                "type": "string",
                                "enum": _HIGHLIGHT_SECTIONS,
                            },
                            "item_id": {
                                "type": "string",
                                "description": "经历/项目/教育条目的 id",
                            },
                            "text": {
                                "type": "string",
                                "description": "新增的亮点文本",
                            },
                        },
                        "required": ["section", "item_id", "text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "remove_highlight",
                    "description": "从某个条目删除一条 highlight。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "section": {
                                "type": "string",
                                "enum": _HIGHLIGHT_SECTIONS,
                            },
                            "item_id": {
                                "type": "string",
                                "description": "经历/项目/教育条目的 id",
                            },
                            "highlight_id": {
                                "type": "string",
                                "description": "要删除的亮点 id",
                            },
                        },
                        "required": ["section", "item_id", "highlight_id"],
                    },
                },
            },
        ]

    @classmethod
    def execute_tool(cls, tool_name: str, resume_content: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        tool_map = {
            "read_resume": cls.read_resume,
            "update_overview": cls.update_overview,
            "update_highlight": cls.update_highlight,
            "add_highlight": cls.add_highlight,
            "remove_highlight": cls.remove_highlight,
        }
        if tool_name not in tool_map:
            return {"error": f"Unknown tool: {tool_name}"}
        return tool_map[tool_name](resume_content, **kwargs)


__all__ = [
    "read_resume_content",
    "update_overview",
    "update_highlight",
    "add_highlight",
    "remove_highlight",
    "ResumeTools",
]
