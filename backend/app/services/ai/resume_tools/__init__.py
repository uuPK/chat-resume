"""
简历优化工具集合
"""

from typing import Dict, Any, List

from .read_resume import read_resume_content
from .edit_resume import (
    edit_resume_content,
    update_resume_item,
    add_resume_item,
    remove_resume_item,
)

_ARRAY_SECTIONS = ["education", "work_experience", "skills", "projects", "languages"]
_ALL_SECTIONS = _ARRAY_SECTIONS + ["personal_info", "summary"]


class ResumeTools:
    """提供AI可调用的工具集合"""

    @staticmethod
    def read_resume(resume_content: Dict[str, Any]) -> Dict[str, Any]:
        return read_resume_content(resume_content)

    @staticmethod
    def edit_resume(resume_content: Dict[str, Any], section: str, data: Any) -> Dict[str, Any]:
        return edit_resume_content(resume_content, section, data)

    @staticmethod
    def update_resume_item(resume_content: Dict[str, Any], section: str, item_id: str, patch: Any) -> Dict[str, Any]:
        return update_resume_item(resume_content, section, item_id, patch)

    @staticmethod
    def add_resume_item(resume_content: Dict[str, Any], section: str, item: Any) -> Dict[str, Any]:
        return add_resume_item(resume_content, section, item)

    @staticmethod
    def remove_resume_item(resume_content: Dict[str, Any], section: str, item_id: str) -> Dict[str, Any]:
        return remove_resume_item(resume_content, section, item_id)

    @classmethod
    def get_tools_schema(cls) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "edit_resume",
                    "description": (
                        "替换整个板块的内容（适合 personal_info、summary 等非数组板块，"
                        "或需要大幅重写整个数组时使用）。"
                        "对数组板块的单条修改请优先用 update_resume_item。"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "section": {
                                "type": "string",
                                "enum": _ALL_SECTIONS,
                                "description": "要替换的板块",
                            },
                            "data": {
                                "type": "string",
                                "description": "该板块的完整新数据（JSON 字符串）",
                            },
                        },
                        "required": ["section", "data"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "update_resume_item",
                    "description": (
                        "精准更新数组板块（education/work_experience/skills/projects/languages）"
                        "中某个条目的部分字段。"
                        "比 edit_resume 省 token，推荐用于只改某条经历的描述或亮点。"
                        "item_id 在简历 JSON 中每个条目的 id 字段里。"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "section": {
                                "type": "string",
                                "enum": _ARRAY_SECTIONS,
                                "description": "数组板块名",
                            },
                            "item_id": {
                                "type": "string",
                                "description": "要修改的条目 id",
                            },
                            "patch": {
                                "type": "string",
                                "description": "要更新的字段（JSON 对象字符串），只需包含要改的字段，其余字段保持不变",
                            },
                        },
                        "required": ["section", "item_id", "patch"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "add_resume_item",
                    "description": "向数组板块末尾追加一个新条目（如新增一段工作经历或一个项目）。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "section": {
                                "type": "string",
                                "enum": _ARRAY_SECTIONS,
                                "description": "目标板块",
                            },
                            "item": {
                                "type": "string",
                                "description": "新条目数据（JSON 对象字符串），无需填写 id",
                            },
                        },
                        "required": ["section", "item"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "remove_resume_item",
                    "description": "从数组板块中删除指定 id 的条目。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "section": {
                                "type": "string",
                                "enum": _ARRAY_SECTIONS,
                                "description": "目标板块",
                            },
                            "item_id": {
                                "type": "string",
                                "description": "要删除的条目 id",
                            },
                        },
                        "required": ["section", "item_id"],
                    },
                },
            },
        ]

    @classmethod
    def execute_tool(cls, tool_name: str, resume_content: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        tool_map = {
            "read_resume": cls.read_resume,
            "edit_resume": cls.edit_resume,
            "update_resume_item": cls.update_resume_item,
            "add_resume_item": cls.add_resume_item,
            "remove_resume_item": cls.remove_resume_item,
        }
        if tool_name not in tool_map:
            return {"error": f"Unknown tool: {tool_name}"}
        return tool_map[tool_name](resume_content, **kwargs)


__all__ = [
    "read_resume_content",
    "edit_resume_content",
    "update_resume_item",
    "add_resume_item",
    "remove_resume_item",
    "ResumeTools",
]
