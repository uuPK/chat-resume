"""
AI服务模块

提供统一的AI服务接口，包括面试Agent、聊天服务、响应解析器等。
符合团队代码编写规范，确保模块间的低耦合和高内聚。
"""

from .interview_agent import InterviewAgent
from .chat_service import ChatService, AIProvider
from .interview_response_parser import InterviewResponseParser
from .interview_data_structures import (
    InterviewQuestion,
    InterviewFeedback,
    FollowUpQuestion,
    InterviewEvaluation,
    InterviewTips,
    QuestionGenerationResult,
    InterviewConversationResult,
    QuestionType,
    DifficultyLevel,
    RecommendationType,
    CategoryScore,
    InterviewSession,
)

__all__ = [
    "InterviewAgent",
    "ChatService",
    "AIProvider",
    "InterviewResponseParser",
    "InterviewQuestion",
    "InterviewFeedback",
    "FollowUpQuestion",
    "InterviewEvaluation",
    "InterviewTips",
    "QuestionGenerationResult",
    "InterviewConversationResult",
    "QuestionType",
    "DifficultyLevel",
    "RecommendationType",
    "CategoryScore",
    "InterviewSession",
]
