"""
简历优化工具集合
"""

from typing import Dict, Any, List

from .scoring import score_resume
from .login_full_auto import login_full_auto
from .login_start_interactive import login_start_interactive
from .login_info import get_login_info
from .job_recommendations import get_recommend_jobs
from .greeting import send_greeting


class ResumeTools:
    """提供AI可调用的工具集合"""

    @staticmethod
    def score_resume(
        resume_content: Dict[str, Any], criteria: str = "comprehensive"
    ) -> Dict[str, Any]:
        """对简历评分"""
        return score_resume(resume_content, criteria)

    @staticmethod
    def login_full_auto(resume_content: Dict[str, Any]) -> Dict[str, Any]:
        """触发Boss直聘自动登录"""
        return login_full_auto(resume_content)

    @staticmethod
    def login_start_interactive(resume_content: Dict[str, Any]) -> Dict[str, Any]:
        """触发Boss直聘交互式登录"""
        return login_start_interactive(resume_content)

    @staticmethod
    def get_login_info(resume_content: Dict[str, Any]) -> Dict[str, Any]:
        """查询Boss直聘登录状态"""
        return get_login_info(resume_content)

    @staticmethod
    def get_recommend_jobs(
        resume_content: Dict[str, Any],
        page: int = 1,
        experience: str = "不限",
        job_type: str = "全职",
        salary: str = "不限",
    ) -> Dict[str, Any]:
        """获取Boss直聘职位推荐"""
        return get_recommend_jobs(resume_content, page, experience, job_type, salary)

    @staticmethod
    def send_greeting(
        resume_content: Dict[str, Any],
        security_id: str,
        job_id: str,
        message: str = "您好，我对这个职位很感兴趣，希望可以进一步沟通",
    ) -> Dict[str, Any]:
        """向Boss直聘职位发送打招呼"""
        return send_greeting(resume_content, security_id, job_id, message)

    @classmethod
    def get_tools_schema(cls) -> List[Dict[str, Any]]:
        """获取工具Schema"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "score_resume",
                    "description": "对简历进行综合评分，分析优缺点",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "criteria": {
                                "type": "string",
                                "enum": ["comprehensive", "technical", "presentation"],
                                "description": "评分标准：comprehensive-综合评估，technical-技术能力，presentation-展示效果",
                            }
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "login_full_auto",
                    "description": "启动Boss直聘自动登录流程，自动监控扫码状态",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "login_start_interactive",
                    "description": "与用户交互式完成Boss直聘扫码登录流程",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_login_info",
                    "description": "查询Boss直聘登录状态以及Cookie等信息",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_recommend_jobs",
                    "description": "根据筛选条件获取Boss直聘推荐职位列表",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "page": {"type": "integer", "description": "页码，从1开始"},
                            "experience": {
                                "type": "string",
                                "description": "经验要求，如不限、应届生、一到三年等",
                            },
                            "job_type": {
                                "type": "string",
                                "description": "工作类型，如全职、兼职",
                            },
                            "salary": {
                                "type": "string",
                                "description": "薪资范围，如10-20k",
                            },
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "send_greeting",
                    "description": "向Boss直聘上的职位发送打招呼信息",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "security_id": {"type": "string", "description": "职位安全ID"},
                            "job_id": {"type": "string", "description": "职位ID"},
                            "message": {
                                "type": "string",
                                "description": "打招呼内容",
                            },
                        },
                        "required": ["security_id", "job_id"],
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
            "score_resume": cls.score_resume,
            "login_full_auto": cls.login_full_auto,
            "login_start_interactive": cls.login_start_interactive,
            "get_login_info": cls.get_login_info,
            "get_recommend_jobs": cls.get_recommend_jobs,
            "send_greeting": cls.send_greeting,
        }

        if tool_name not in tool_map:
            return {"error": f"Unknown tool: {tool_name}"}

        return tool_map[tool_name](resume_content, **kwargs)


__all__ = [
    "score_resume",
    "login_full_auto",
    "login_start_interactive",
    "get_login_info",
    "get_recommend_jobs",
    "send_greeting",
    "ResumeTools",
]
