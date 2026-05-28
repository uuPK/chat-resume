"""
学习路线接口

处理获取、生成学习路线以及 PDF/Word 导出的相关请求。
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infra.database import get_db
from app.services.errors import ServiceError
from app.entrypoints.http.deps import get_current_user
from app.models.interview import InterviewSession
from app.models.learning_path import LearningPathVersion
from app.models.resume import Resume
from app.services.learning_path.plan_service import generate_learning_path

router = APIRouter()

@router.get("/resumes/{resume_id}/learning-paths")
async def list_learning_paths(
    resume_id: int = Path(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """获取指定简历的所有学习路线版本历史。"""
    resume = db.scalar(select(Resume).where(Resume.id == resume_id, Resume.owner_id == current_user["id"]))
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
        
    versions = db.scalars(
        select(LearningPathVersion)
        .where(LearningPathVersion.resume_id == resume_id)
        .order_by(LearningPathVersion.created_at.desc())
    ).all()
    
    return [
        {
            "id": v.id,
            "trigger_type": v.trigger_type,
            "interview_session_id": v.interview_session_id,
            "plan_data": v.plan_data,
            "created_at": v.created_at.isoformat(),
        }
        for v in versions
    ]

@router.post("/resumes/{resume_id}/learning-paths")
async def create_learning_path_from_resume(
    resume_id: int = Path(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """基于当前简历内容，一键生成最新的学习路线。"""
    resume = db.scalar(select(Resume).where(Resume.id == resume_id, Resume.owner_id == current_user["id"]))
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
        
    try:
        new_version = await generate_learning_path(db, resume_id, "resume_update")
    except ServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
        
    return {
        "id": new_version.id,
        "plan_data": new_version.plan_data,
        "created_at": new_version.created_at.isoformat(),
    }

@router.post("/interviews/{session_id}/learning-paths")
async def create_learning_path_from_interview(
    session_id: int = Path(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """基于某场面试结果生成或更新学习路线。"""
    session = db.scalar(select(InterviewSession).where(InterviewSession.id == session_id, InterviewSession.user_id == current_user["id"]))
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found")
        
    try:
        new_version = await generate_learning_path(db, session.resume_id, "interview_completed", session_id)
    except ServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
        
    return {
        "id": new_version.id,
        "plan_data": new_version.plan_data,
        "created_at": new_version.created_at.isoformat(),
    }

@router.get("/learning-paths/{path_id}/export/{format}")
async def export_learning_path(
    format: str = Path(..., description="pdf or docx"),
    path_id: int = Path(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """导出学习路线。"""
    if format not in ["pdf", "docx"]:
        raise HTTPException(status_code=400, detail="Unsupported format")
        
    version = db.scalar(select(LearningPathVersion).where(LearningPathVersion.id == path_id))
    if not version:
        raise HTTPException(status_code=404, detail="Learning path not found")
        
    # 权限校验: 需要拥有对应resume
    resume = db.scalar(select(Resume).where(Resume.id == version.resume_id, Resume.owner_id == current_user["id"]))
    if not resume:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    from app.services.processing.export_service import ExportService
    from fastapi.responses import FileResponse
    import os
    
    export_svc = ExportService()
    try:
        if format == "pdf":
            filepath = await export_svc.export_learning_path_to_pdf(version.plan_data)
            media_type = "application/pdf"
        else:
            filepath = export_svc.export_learning_path_to_docx(version.plan_data)
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            
        filename = os.path.basename(filepath)
        return FileResponse(
            path=filepath,
            filename=filename,
            media_type=media_type,
            background=None, # File cleanup can be implemented here using background tasks if needed
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(exc)}")
