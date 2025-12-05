"""
Boss直聘打招呼工具
"""

from typing import Dict, Any

from .boss_client import send_greeting_request


def send_greeting(
    resume_content: Dict[str, Any],
    security_id: str,
    job_id: str,
    message: str = "您好，我对这个职位很感兴趣，希望可以进一步沟通",
) -> Dict[str, Any]:
    """向指定职位发送打招呼"""
    result = send_greeting_request(security_id, job_id)
    result["tool"] = "send_greeting"
    result["request_message"] = message
    return result
