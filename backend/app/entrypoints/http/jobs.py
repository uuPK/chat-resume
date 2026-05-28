"""
智能岗位推荐API端点模块

提供简历匹配岗位和生成深度匹配报告的API。
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.entrypoints.http.deps import get_current_user_claims
from app.infra.database import get_db
from app.services.job_recommendation.service import JobRecommendationService
from app.services.domain.resume_service import ResumeService

router = APIRouter()
logger = logging.getLogger(__name__)


class JobRecommendationResponse(BaseModel):
    id: int
    resume_id: int
    recommendations: list[dict[str, Any]]
    
    model_config = {"from_attributes": True}


class JobMatchReportRequest(BaseModel):
    target_jd: str


class JobMatchReportResponse(BaseModel):
    id: int
    resume_id: int
    target_jd: str
    analysis_result: dict[str, Any]
    
    model_config = {"from_attributes": True}


def _check_resume_access(
    resume_id: int,
    user_id: int,
    db: Session,
):
    """验证用户对指定简历的访问权限"""
    resume_service = ResumeService(db)
    resume = resume_service.get_by_id(resume_id)
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found"
        )
    if resume.owner_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )
    return resume


@router.get("/{resume_id}/job-recommendations", response_model=JobRecommendationResponse)
async def get_job_recommendations(
    resume_id: int,
    current_user: dict = Depends(get_current_user_claims),
    db: Session = Depends(get_db),
):
    """获取指定简历最新生成的岗位推荐列表"""
    _check_resume_access(resume_id, current_user["id"], db)
    
    service = JobRecommendationService(db)
    recommendation = service.get_latest_recommendations(resume_id)
    
    if not recommendation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job recommendations not found for this resume"
        )
        
    return recommendation


@router.post("/{resume_id}/job-recommendations", response_model=JobRecommendationResponse)
async def generate_job_recommendations(
    resume_id: int,
    current_user: dict = Depends(get_current_user_claims),
    db: Session = Depends(get_db),
):
    """主动触发大模型为指定简历生成最新的岗位推荐列表"""
    _check_resume_access(resume_id, current_user["id"], db)
    
    service = JobRecommendationService(db)
    try:
        recommendation = await service.generate_recommendations(resume_id)
        return recommendation
    except Exception as e:
        logger.exception(f"Failed to generate job recommendations for resume {resume_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/{resume_id}/match-report", response_model=JobMatchReportResponse)
async def generate_match_report(
    resume_id: int,
    request: JobMatchReportRequest,
    current_user: dict = Depends(get_current_user_claims),
    db: Session = Depends(get_db),
):
    """给定目标职位JD，为简历生成深度匹配分析报告"""
    _check_resume_access(resume_id, current_user["id"], db)
    
    if not request.target_jd or len(request.target_jd.strip()) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valid target_jd is required",
        )
        
    service = JobRecommendationService(db)
    try:
        report = await service.generate_match_report(resume_id, request.target_jd)
        return report
    except Exception as e:
        logger.exception(f"Failed to generate match report for resume {resume_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
