"""面试相关数据模式"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class InterviewSessionCreate(BaseModel):
    """创建面试会话"""

    job_position: Optional[str] = None
    jd_content: Optional[str] = None


class InterviewTurn(BaseModel):
    """单轮面试记录"""

    turn_index: int
    question: str
    question_type: str = "general"
    intent: Optional[str] = None
    answer: Optional[str] = None
    evaluation: Optional[Dict[str, Any]] = None
    score: Optional[int] = None
    status: str = "asked"


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
    overall_score: Optional[int] = None
    resume_title: Optional[str] = None
    turns: List[InterviewTurn] = []
    current_turn: Optional[InterviewTurn] = None
    total_questions: int = 0
    answered_questions: int = 0
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
    session_status: str
    completed: bool = False
    current_turn: Optional[InterviewTurn] = None
    next_turn: Optional[InterviewTurn] = None
