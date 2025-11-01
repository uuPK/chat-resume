"""
AI服务模块

提供统一的AI服务接口，整合多个AI模型提供商。
包括聊天对话、简历优化、面试分析等功能。
"""

from .chat_service import ChatService
from .resume_optimizer import ResumeOptimizer
from .interview_agent import InterviewAgent

__all__ = ["ChatService", "ResumeOptimizer", "InterviewAgent"]
