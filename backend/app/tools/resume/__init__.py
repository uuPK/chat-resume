"""用于集中暴露简历编辑相关的顶层工具。"""

from .add_highlight_tool import add_highlight
from .read_resume_tool import read_resume_content
from .registry import RESUME_TOOLS_SCHEMA, execute_resume_tool
from .remove_highlight_tool import remove_highlight
from .update_highlight_tool import update_highlight
from .update_overview_tool import update_overview

__all__ = [
    "RESUME_TOOLS_SCHEMA",
    "add_highlight",
    "execute_resume_tool",
    "read_resume_content",
    "remove_highlight",
    "update_highlight",
    "update_overview",
]
