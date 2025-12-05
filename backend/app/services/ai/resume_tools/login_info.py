"""
Boss直聘登录状态查询工具
"""

from typing import Dict, Any

from .boss_client import get_login_status


def get_login_info(resume_content: Dict[str, Any]) -> Dict[str, Any]:
    """返回当前登录状态"""
    status = get_login_status()
    status.update({"tool": "get_login_info"})
    return status
