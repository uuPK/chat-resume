from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any, cast
from app.core.database import get_db
from app.services.core import ResumeService
from app.schemas.resume import OptimizationRequest, OptimizationResponse
from app.models.resume import OptimizationRecord
from app.api.deps import get_current_user

router = APIRouter()


@router.post("/{resume_id}/optimize", response_model=OptimizationResponse)
async def optimize_resume(
    resume_id: int,
    optimization_request: OptimizationRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """优化简历"""

    # 获取简历
    resume_service = ResumeService(db)
    resume = resume_service.get_by_id(resume_id)

    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found"
        )

    if resume.owner_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    try:
        # 使用 ChatService 进行分析
        from app.services.ai import ChatService
        from app.services.ai.chat_service import AIProvider

        chat_service = ChatService(AIProvider.OPENROUTER)
        # 确保 resume.content 是字典类型
        resume_content = cast(Dict[str, Any], resume.content or {})

        # 构建分析提示
        system_prompt = """
        你是一位专业的简历优化专家。请分析简历与职位描述的匹配度，
        提供具体的优化建议，包括：
        1. 技能匹配度分析
        2. 经历相关性评估
        3. 具体优化建议
        4. 关键词补充建议
        """

        message = f"""
        简历内容：
        {str(resume_content)}

        职位描述：
        {optimization_request.jd_content}

        请提供详细的简历优化分析和建议。
        """

        analysis_result = await chat_service.chat_with_context(
            message=message, system_prompt=system_prompt
        )

        # 保存优化记录
        optimization_record = OptimizationRecord(
            resume_id=resume_id,
            jd_content=optimization_request.jd_content,
            suggestions=analysis_result,
        )
        db.add(optimization_record)
        db.commit()
        db.refresh(optimization_record)

        return OptimizationResponse.model_validate(optimization_record)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to optimize resume: {str(e)}",
        )


@router.get("/{resume_id}/optimizations")
async def get_optimizations(
    resume_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取简历的优化记录"""

    # 验证简历权限
    resume_service = ResumeService(db)
    resume = resume_service.get_by_id(resume_id)

    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found"
        )

    if resume.owner_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    # 获取优化记录
    optimizations = (
        db.query(OptimizationRecord)
        .filter(OptimizationRecord.resume_id == resume_id)
        .order_by(OptimizationRecord.created_at.desc())
        .all()
    )

    return [OptimizationResponse.model_validate(opt) for opt in optimizations]
