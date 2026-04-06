"""
面试Chatbot模块

简单的AI面试对话服务，复用统一 AgentRuntime。
"""

from typing import Any, Dict, Optional, List
from enum import Enum
from pydantic import BaseModel
from .agent_runtime import AgentDefinition, AgentRuntime
from app.prompts import load_prompt


class QuestionType(str, Enum):
    """问题类型枚举"""

    GENERAL = "general"
    TECHNICAL = "technical"
    BEHAVIORAL = "behavioral"
    SITUATIONAL = "situational"
    FOLLOW_UP = "follow_up"


class FollowUpQuestionResult(BaseModel):
    """追问结果"""

    follow_up_question: str
    question_type: QuestionType
    purpose: str


class InterviewFeedback(BaseModel):
    """面试反馈"""

    score: int
    feedback: str
    improvements: List[str]



class InterviewAgent:
    """AI面试官Chatbot"""

    def __init__(self):
        self.prompt_spec = load_prompt("interview_agent")
        self.runtime = AgentRuntime()
        self.definition = AgentDefinition(
            prompt_spec=self.prompt_spec,
            tools_schema=[],
            tool_executor=self._run_tool,
            prompt_context_builder=self._build_prompt_context,
            max_iterations=1,
        )

    async def chat(
        self,
        message: str,
        job_title: Optional[str] = None,
        job_description: Optional[str] = None,
        resume_content: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """面试对话

        Args:
            message: 用户消息
            job_title: 职位名称
            job_description: 职位描述
            resume_content: 简历内容
            conversation_history: 对话历史

        Returns:
            AI回复
        """
        runtime_result = await self.runtime.run(
            agent=self.definition,
            user_message=message,
            context={
                "job_title": job_title or "",
                "job_description": job_description or "",
                "resume_content": resume_content or "",
            },
            conversation_history=conversation_history,
        )
        return runtime_result["content"]

    def _build_prompt_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "job_title": context.get("job_title", ""),
            "job_description": context.get("job_description", ""),
            "resume_content": context.get("resume_content", ""),
        }

    def _run_tool(
        self, tool_call: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        raise RuntimeError("InterviewAgent does not support tool calls")
