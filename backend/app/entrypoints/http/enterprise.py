from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.infra.database import get_db
from app.entrypoints.http.deps import get_current_user
from app.schemas.enterprise import (
    EnterpriseJobCreate,
    EnterpriseJobUpdate,
    EnterpriseJobResponse,
    JobDeliveryCreate,
    JobDeliveryResponse,
    DeliveryWithDetailsResponse,
    MatchAnalysisRequest
)
from app.services.domain.enterprise_service import EnterpriseService
from app.services.domain.user_service import UserService
from app.services.domain.resume_service import ResumeService

router = APIRouter(prefix="/enterprise", tags=["enterprise"])

def require_enterprise_role(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    if current_user.get("role") != "enterprise":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires enterprise role"
        )
    return current_user

@router.post("/jobs", response_model=EnterpriseJobResponse)
def create_job(
    job_in: EnterpriseJobCreate,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_enterprise_role)
):
    service = EnterpriseService(db)
    return service.create_job(enterprise_id=current_user["id"], job_in=job_in)

@router.get("/jobs", response_model=List[EnterpriseJobResponse])
def list_jobs(
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_enterprise_role)
):
    service = EnterpriseService(db)
    return service.get_jobs_by_enterprise(enterprise_id=current_user["id"])

@router.get("/deliveries", response_model=List[DeliveryWithDetailsResponse])
def get_deliveries(
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_enterprise_role)
):
    service = EnterpriseService(db)
    user_service = UserService(db)
    resume_service = ResumeService(db)
    
    deliveries = service.get_deliveries_for_enterprise(enterprise_id=current_user["id"])
    
    result = []
    for d in deliveries:
        # Load candidate name
        candidate = user_service.get_by_id(d.candidate_id)
        # Load resume title
        resume = resume_service.get_by_id(d.resume_id)
        # Load job title
        job = service.get_job(d.job_id)
        
        d_dict = {
            "id": d.id,
            "job_id": d.job_id,
            "candidate_id": d.candidate_id,
            "resume_id": d.resume_id,
            "status": d.status,
            "match_score": d.match_score,
            "analysis_result": d.analysis_result,
            "created_at": d.created_at,
            "updated_at": d.updated_at,
            "candidate_name": (candidate.full_name or "Unknown") if candidate else "Unknown",
            "resume_title": (resume.title or "未命名简历") if resume else "未命名简历",
            "job_title": (job.title or "Unknown Job") if job else "Unknown Job"
        }
        result.append(d_dict)
        
    return result

# Candidate endpoints for applying to jobs
@router.post("/deliver", response_model=JobDeliveryResponse)
def deliver_resume(
    delivery_in: JobDeliveryCreate,
    resume_id: int,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user)
):
    if current_user.get("role") != "candidate":
        raise HTTPException(status_code=403, detail="Only candidates can deliver resumes")
        
    service = EnterpriseService(db)
    
    # Check job exists
    job = service.get_job(delivery_in.job_id)
    if not job or not job.is_active:
        raise HTTPException(status_code=404, detail="Job not found or inactive")
        
    # Check resume belongs to user
    resume_service = ResumeService(db)
    resume = resume_service.get_by_id(resume_id)
    if not resume or resume.owner_id != current_user["id"]:
        raise HTTPException(status_code=404, detail="Resume not found")
        
    return service.create_delivery(candidate_id=current_user["id"], resume_id=resume_id, delivery_in=delivery_in)

@router.get("/all-jobs", response_model=List[EnterpriseJobResponse])
def get_all_active_jobs(
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user)
):
    """求职者浏览所有活跃岗位的接口"""
    from app.models.enterprise import EnterpriseJob
    jobs = db.query(EnterpriseJob).filter(EnterpriseJob.is_active == True).order_by(EnterpriseJob.created_at.desc()).all()
    return jobs

@router.get("/my-deliveries", response_model=List[DeliveryWithDetailsResponse])
def get_my_deliveries(
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user)
):
    """求职者查看自己的投递记录"""
    if current_user.get("role") != "candidate":
        raise HTTPException(status_code=403, detail="Only candidates can view their deliveries")
        
    service = EnterpriseService(db)
    user_service = UserService(db)
    resume_service = ResumeService(db)
    
    deliveries = service.get_deliveries_for_candidate(candidate_id=current_user["id"])
    
    result = []
    for d in deliveries:
        # Load candidate name
        candidate = user_service.get_by_id(d.candidate_id)
        # Load resume title
        resume = resume_service.get_by_id(d.resume_id)
        # Load job title
        job = service.get_job(d.job_id)
        
        d_dict = {
            "id": d.id,
            "job_id": d.job_id,
            "candidate_id": d.candidate_id,
            "resume_id": d.resume_id,
            "status": d.status,
            "match_score": d.match_score,
            "analysis_result": d.analysis_result,
            "created_at": d.created_at,
            "updated_at": d.updated_at,
            "candidate_name": (candidate.full_name or "Unknown") if candidate else "Unknown",
            "resume_title": (resume.title or "未命名简历") if resume else "未命名简历",
            "job_title": (job.title or "Unknown Job") if job else "Unknown Job"
        }
        result.append(d_dict)
        
    return result

@router.get("/deliveries/{delivery_id}", response_model=DeliveryWithDetailsResponse)
def get_delivery(
    delivery_id: int,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_enterprise_role)
):
    service = EnterpriseService(db)
    user_service = UserService(db)
    resume_service = ResumeService(db)
    
    d = service.get_delivery(delivery_id=delivery_id, enterprise_id=current_user["id"])
    
    # Load candidate name
    candidate = user_service.get_by_id(d.candidate_id)
    # Load resume title
    resume = resume_service.get_by_id(d.resume_id)
    # Load job title
    job = service.get_job(d.job_id)
    
    return {
        "id": d.id,
        "job_id": d.job_id,
        "candidate_id": d.candidate_id,
        "resume_id": d.resume_id,
        "status": d.status,
        "match_score": d.match_score,
        "analysis_result": d.analysis_result,
        "created_at": d.created_at,
        "updated_at": d.updated_at,
        "candidate_name": (candidate.full_name or "Unknown") if candidate else "Unknown",
        "resume_title": (resume.title or "未命名简历") if resume else "未命名简历",
        "job_title": (job.title or "Unknown Job") if job else "Unknown Job"
    }

@router.get("/deliveries/{delivery_id}/resume")
def get_delivery_resume(
    delivery_id: int,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_enterprise_role)
):
    """企业查看投递简历的内容"""
    service = EnterpriseService(db)
    delivery = service.get_delivery(delivery_id=delivery_id, enterprise_id=current_user["id"])
    
    resume_service = ResumeService(db)
    resume = resume_service.get_by_id(delivery.resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
        
    from app.entrypoints.http.resumes import _build_resume_response
    return _build_resume_response(resume)

@router.post("/analyze-match", response_model=JobDeliveryResponse)
def analyze_delivery_match(
    request: MatchAnalysisRequest,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_enterprise_role)
):
    """调用大模型为企业的某一份投递生成匹配报告与面试问题"""
    service = EnterpriseService(db)
    delivery = service.get_delivery(delivery_id=request.delivery_id, enterprise_id=current_user["id"])
    
    if delivery.analysis_result:
        return delivery # Already analyzed
        
    # TODO: Call actual LLM. For now, returning mocked analysis.
    job = service.get_job(delivery.job_id)
    resume_service = ResumeService(db)
    resume = resume_service.get_by_id(delivery.resume_id)
    
    mock_score = 85
    mock_analysis = {
        "summary": f"该候选人与{job.title}岗位的匹配度较高。拥有相关技能储备。",
        "strengths": ["技术栈对口", "有相关项目经验"],
        "weaknesses": ["可能缺少某些高并发场景下的实践"],
        "interview_questions": [
            "请详细描述你在上个项目中是如何使用React的？",
            "遇到复杂状态管理时，你更倾向于哪种方案？为什么？",
            "如果页面加载过慢，你会从哪些方面进行排查和优化？"
        ]
    }
    
    return service.update_delivery_match(delivery, match_score=mock_score, analysis_result=mock_analysis)
