"""
Boss直聘交互式登录工具
"""

from typing import Dict, Any

from .boss_client import start_login


def login_start_interactive(resume_content: Dict[str, Any]) -> Dict[str, Any]:
    """开启交互式登录流程（目前与自动登录一致）"""
    result = start_login(auto_mode=False)
    result["tool"] = "login_start_interactive"
    return result
