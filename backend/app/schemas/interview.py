"""
面试相关数据模式
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel


class InterviewSessionCreate(BaseModel):
    """创建面试会话"""

    job_position: Optional[str] = None
    jd_content: Optional[str] = None


class InterviewSessionResponse(BaseModel):
    """面试会话响应"""

    id: int
    resume_id: int
    job_position: Optional[str] = None
    jd_content: Optional[str] = None
    questions: List[Dict[str, Any]]
    answers: List[Dict[str, Any]]
    feedback: Dict[str, Any]
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class InterviewQuestionResponse(BaseModel):
    """面试问题响应"""

    question: str
    question_type: str
    question_index: int


class InterviewAnswerRequest(BaseModel):
    """面试回答请求"""

    answer: str
    question_index: int


class InterviewEvaluationResponse(BaseModel):
    """面试评估响应"""

    question: str
    answer: str
    evaluation: Dict[str, Any]
    score: int
    feedback: str
    suggestions: List[str]
