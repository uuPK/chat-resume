"""
简历优化工具集合
"""

from typing import Dict, Any, List

from .read_resume import read_resume_content
from .edit_resume import edit_resume_content


class ResumeTools:
    """提供AI可调用的工具集合"""

    @staticmethod
    def read_resume(resume_content: Dict[str, Any]) -> Dict[str, Any]:
        """读取简历完整内容"""
        return read_resume_content(resume_content)

    @staticmethod
    def edit_resume(
        resume_content: Dict[str, Any], section: str, data: Any
    ) -> Dict[str, Any]:
        """编辑简历内容"""
        return edit_resume_content(resume_content, section, data)

    @classmethod
    def get_tools_schema(cls) -> List[Dict[str, Any]]:
        """获取工具Schema（简历内容已在系统提示词中，无需 read_resume）"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "edit_resume",
                    "description": "编辑简历特定板块的内容。data 必须是该板块的完整新数据（JSON格式）",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "section": {
                                "type": "string",
                                "enum": [
                                    "personal_info",
                                    "education",
                                    "work_experience",
                                    "skills",
                                    "projects",
                                    "summary",
                                    "languages",
                                ],
                                "description": "要修改的简历板块",
                            },
                            "data": {
                                "type": "string",
                                "description": "该板块的完整新数据（JSON格式）。注意：这是替换而非增量更新",
                            },
                        },
                        "required": ["section", "data"],
                    },
                },
            },
        ]

    @classmethod
    def execute_tool(
        cls, tool_name: str, resume_content: Dict[str, Any], **kwargs
    ) -> Dict[str, Any]:
        """执行工具调用"""
        tool_map = {
            "read_resume": cls.read_resume,
            "edit_resume": cls.edit_resume,
        }

        if tool_name not in tool_map:
            return {"error": f"Unknown tool: {tool_name}"}

        return tool_map[tool_name](resume_content, **kwargs)


__all__ = [
    "read_resume_content",
    "edit_resume_content",
    "ResumeTools",
]
