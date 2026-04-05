"""
面试Chatbot模块

简单的AI面试对话服务，动态插入面试相关信息到提示词中。
"""

from typing import Optional, List, Dict
from enum import Enum
from pydantic import BaseModel
from .chat_service import ChatService
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
        self.chat_service = ChatService()
        self.prompt_spec = load_prompt("interview_agent")

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
        system_prompt = self.prompt_spec.render(
            job_title=job_title or "",
            job_description=job_description or "",
            resume_content=resume_content or "",
        )

        return await self.chat_service.chat_with_context(
            message=message,
            system_prompt=system_prompt,
            conversation_history=conversation_history,
        )
