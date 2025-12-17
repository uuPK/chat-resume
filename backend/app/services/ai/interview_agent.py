"""
面试Chatbot模块

简单的AI面试对话服务，动态插入面试相关信息到提示词中。
"""

from typing import Optional, List, Dict
from enum import Enum
from pydantic import BaseModel
from .chat_service import ChatService


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


class InterviewEvaluation(BaseModel):
    """面试评估结果"""

    feedback: InterviewFeedback
    strengths: List[str]
    weaknesses: List[str]
    overall_assessment: str


class InterviewPerformanceResult(BaseModel):
    """面试表现评估结果"""

    total_score: int
    detailed_scores: Dict[str, int]
    strengths: List[str]
    weaknesses: List[str]
    recommendations: List[str]
    overall_assessment: str


class InterviewAgent:
    """AI面试官Chatbot"""

    def __init__(self):
        self.chat_service = ChatService()

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
        system_prompt = self._build_system_prompt(
            job_title, job_description, resume_content
        )

        return await self.chat_service.chat_with_context(
            message=message,
            system_prompt=system_prompt,
            conversation_history=conversation_history,
        )

    def _build_system_prompt(
        self,
        job_title: Optional[str],
        job_description: Optional[str],
        resume_content: Optional[str],
    ) -> str:
        """构建系统提示词"""
        prompt = "你是一位专业的AI面试官，负责对候选人进行面试评估。\n\n"

        if job_title:
            prompt += f"目标职位：{job_title}\n\n"

        if job_description:
            prompt += f"职位描述：\n{job_description}\n\n"

        if resume_content:
            prompt += f"候选人简历：\n{resume_content}\n\n"

        prompt += """你的职责是：
1. 根据职位要求和候选人简历进行针对性提问
2. 对候选人的回答进行专业评估和反馈
3. 在面试过程中保持专业、友好的态度
4. 根据候选人表现进行追问或深入探讨
5. 最后可以提供综合评估和建议
"""
        return prompt
