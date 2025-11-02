"""
AI提示词管理模块

包含简历优化、面试指导等AI功能的提示词管理。
提供统一的提示词接口和管理功能。
"""

from .resume_prompts import ResumePrompts
from .interview_prompts import InterviewPrompts

__all__ = ["ResumePrompts", "InterviewPrompts"]