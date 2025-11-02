"""
面试数据结构定义模块

定义面试相关的数据结构，确保数据类型明确、结构清晰。
符合团队代码规范中"数据结构是核心"的原则。
"""

from dataclasses import dataclass
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum


class QuestionType(str, Enum):
    """问题类型枚举"""

    BEHAVIORAL = "behavioral"  # 行为问题
    TECHNICAL = "technical"  # 技术问题
    SITUATIONAL = "situational"  # 情景问题
    GENERAL = "general"  # 通用问题
    FOLLOW_UP = "follow_up"  # 追问


class DifficultyLevel(str, Enum):
    """难度级别枚举"""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class RecommendationType(str, Enum):
    """录用建议类型"""

    STRONG_RECOMMEND = "strong_recommend"  # 强烈推荐
    RECOMMEND = "recommend"  # 推荐
    CONSIDER = "consider"  # 考虑
    NOT_RECOMMEND = "not_recommend"  # 不推荐


@dataclass
class InterviewQuestion:
    """面试问题数据结构"""

    question: str  # 问题内容
    question_type: QuestionType  # 问题类型
    purpose: str  # 考察目的
    reference_points: List[str]  # 参考回答要点
    difficulty: DifficultyLevel  # 难度级别
    follow_up_suggestions: Optional[List[str]] = None  # 可能的追问建议

    def __post_init__(self):
        if self.follow_up_suggestions is None:
            self.follow_up_suggestions = []


@dataclass
class InterviewFeedback:
    """面试反馈数据结构"""

    feedback: str  # 反馈内容
    score: int  # 评分 (1-10)
    strengths: List[str]  # 优点分析
    improvements: List[str]  # 改进建议
    follow_up_suggestions: Optional[List[str]] = None  # 追问建议

    def __post_init__(self):
        if self.follow_up_suggestions is None:
            self.follow_up_suggestions = []

        # 参数校验
        if not 1 <= self.score <= 10:
            raise ValueError(f"评分必须在1-10之间，当前值: {self.score}")


@dataclass
class FollowUpQuestion:
    """追问问题数据结构"""

    follow_up_question: str  # 追问内容
    question_type: QuestionType  # 问题类型
    purpose: str  # 追问目的
    level: str  # 追问级别（深入挖掘/引导补充）


@dataclass
class CategoryScore:
    """分类评分数据结构"""

    category: str  # 评分类别
    score: int  # 评分 (1-10)
    description: str  # 评分说明

    def __post_init__(self):
        if not 1 <= self.score <= 10:
            raise ValueError(f"分类评分必须在1-10之间，当前值: {self.score}")


@dataclass
class InterviewEvaluation:
    """面试评估报告数据结构"""

    overall_evaluation: str  # 总体评价
    total_score: int  # 总分 (1-100)
    category_scores: List[CategoryScore]  # 各项能力评分
    recommendation: RecommendationType  # 录用建议
    strengths: List[str]  # 优势和亮点
    weaknesses: List[str]  # 不足和改进建议
    evaluation_date: datetime  # 评估日期

    def __post_init__(self):
        if not 1 <= self.total_score <= 100:
            raise ValueError(f"总分必须在1-100之间，当前值: {self.total_score}")


@dataclass
class InterviewTips:
    """面试技巧建议数据结构"""

    job_title: str  # 目标职位
    interview_tips: str  # 面试技巧内容
    key_areas: List[str]  # 关键准备领域
    common_mistakes: List[str]  # 常见错误
    user_concerns: Optional[List[str]] = None  # 用户关注的问题

    def __post_init__(self):
        if self.user_concerns is None:
            self.user_concerns = []


@dataclass
class InterviewSession:
    """面试会话记录数据结构"""

    question: str  # 面试问题
    answer: str  # 用户回答
    feedback: Optional[str] = None  # 反馈内容
    score: Optional[int] = None  # 评分
    question_type: Optional[QuestionType] = None  # 问题类型
    timestamp: Optional[datetime] = None  # 时间戳

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

        if self.score is not None and not 1 <= self.score <= 10:
            raise ValueError(f"评分必须在1-10之间，当前值: {self.score}")


@dataclass
class QuestionGenerationResult:
    """问题生成结果数据结构"""

    questions: List[InterviewQuestion]  # 生成的问题列表
    total_count: int  # 问题总数
    generation_time: datetime  # 生成时间
    job_title: str  # 职位名称
    difficulty: DifficultyLevel  # 难度级别
    raw_response: Optional[str] = None  # 原始响应

    def __post_init__(self):
        if len(self.questions) != self.total_count:
            raise ValueError("问题列表长度与总数不匹配")


@dataclass
class InterviewConversationResult:
    """面试对话结果数据结构"""

    feedback: InterviewFeedback  # 面试反馈
    follow_up_question: Optional[FollowUpQuestion] = None  # 追问问题
    conversation_history: Optional[List[Dict[str, str]]] = None  # 对话历史

    def __post_init__(self):
        if self.conversation_history is None:
            self.conversation_history = []
