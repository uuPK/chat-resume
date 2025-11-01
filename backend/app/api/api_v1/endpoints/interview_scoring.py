"""
面试评分API端点
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from app.services.core import ResumeService
from app.core.database import get_db
from app.api.deps import get_current_user

router = APIRouter()


class ScoringRequest(BaseModel):
    """评分请求模型"""

    question: str
    answer: str
    resume_id: int
    jd_keywords: Optional[List[str]] = None


class ScoringResponse(BaseModel):
    """评分响应模型"""

    model_config = {"extra": "forbid"}

    relevance_score: float
    star_analysis: Dict[str, bool]
    keyword_match: Dict[str, Any]
    fluency_score: float
    overall_score: float
    suggestions: List[str]


@router.post("/score", response_model=ScoringResponse)
async def score_interview_answer(
    scoring_request: ScoringRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    对面试回答进行多维度评分
    """
    try:
        # 验证简历权限
        resume_service = ResumeService(db)
        resume = resume_service.get_by_id(scoring_request.resume_id)

        if not resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="简历不存在"
            )

        if resume.owner_id != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="没有权限访问此简历"
            )

        # 初始化评分服务 - 使用 InterviewAgent 替代
        from app.services.ai import InterviewAgent
        from app.services.ai.chat_service import AIProvider

        scoring_service = InterviewAgent(AIProvider.OPENROUTER)

        # resume.content 不再需要，InterviewAgent 会直接处理

        # 使用 InterviewAgent 的 conduct_interview 方法进行评估
        result = await scoring_service.conduct_interview(
            question=scoring_request.question,
            user_answer=scoring_request.answer,
            question_context=f"JD关键词: {', '.join(scoring_request.jd_keywords or [])}",
            interview_history=[],
        )

        # 使用 model_construct 方法创建响应实例
        # 从 InterviewAgent 的结果中提取数据
        score = result.get("score", 8)
        improvements = result.get("improvements", [])

        return ScoringResponse.model_construct(
            relevance_score=float(score),
            star_analysis={
                "situation": "N/A",
                "task": "N/A",
                "action": "N/A",
                "result": "N/A",
            },
            keyword_match={"matched": [], "missing": [], "score": 0.8},
            fluency_score=float(score),
            overall_score=float(score * 10),  # 转换为100分制
            suggestions=improvements,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"评分服务暂时不可用: {str(e)}",
        )


@router.get("/keywords")
async def get_tech_keywords():
    """
    获取技术关键词库
    """
    # 返回预设的技术关键词和STAR关键词
    return {
        "tech_keywords": [
            "Python",
            "JavaScript",
            "React",
            "Vue",
            "Node.js",
            "Java",
            "Spring",
            "MySQL",
            "MongoDB",
            "Docker",
            "Kubernetes",
            "AWS",
            "Git",
            "CI/CD",
            "机器学习",
            "深度学习",
            "数据分析",
            "算法",
            "数据结构",
            "系统设计",
        ],
        "star_keywords": [
            "situation",
            "task",
            "action",
            "result",
            "情境",
            "任务",
            "行动",
            "结果",
        ],
    }
