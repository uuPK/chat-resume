"""
Boss直聘自动登录工具
"""

from typing import Dict, Any

from .boss_client import start_login


def login_full_auto(resume_content: Dict[str, Any]) -> Dict[str, Any]:
    """启动自动登录，返回二维码信息"""
    result = start_login(auto_mode=True)
    result["tool"] = "login_full_auto"
    return result
