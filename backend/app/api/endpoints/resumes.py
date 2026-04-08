"""
简历管理API端点模块

提供简历的创建、查询、更新、删除等RESTful API端点。
处理简历相关的所有HTTP请求和响应。
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.resume import (
    ResumeCreate,
    ResumeListItem,
    ResumeProposalResponse,
    ResumeResponse,
    ResumeUpdate,
)
from app.services.core import ResumeService
from app.api.deps import get_current_user

router = APIRouter()


@router.get("/", response_model=List[ResumeListItem])
async def get_resumes(
    current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    resume_service = ResumeService(db)
    resumes = resume_service.get_by_owner(current_user["id"])
    result: list[ResumeListItem] = []
    for resume in resumes:
        content = resume.content if isinstance(resume.content, dict) else {}
        job_application = content.get("job_application", {}) if isinstance(content, dict) else {}
        result.append(
            ResumeListItem.model_validate(
                {
                    "id": resume.id,
                    "title": resume.title,
                    "original_filename": resume.original_filename,
                    "owner_id": resume.owner_id,
                    "created_at": resume.created_at,
                    "updated_at": resume.updated_at,
                    "target_company": str(job_application.get("target_company", "") or ""),
                    "target_title": str(job_application.get("target_title", "") or ""),
                }
            )
        )
    return result


@router.post("/", response_model=ResumeResponse)
async def create_resume(
    resume_create: ResumeCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resume_service = ResumeService(db)
    resume = resume_service.create(resume_create, current_user["id"])
    return ResumeResponse.model_validate(resume)


@router.get("/{resume_id}", response_model=ResumeResponse)
async def get_resume(
    resume_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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

    return ResumeResponse.model_validate(resume)


@router.put("/{resume_id}", response_model=ResumeResponse)
async def update_resume(
    resume_id: int,
    resume_update: ResumeUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新简历"""
    resume_service = ResumeService(db)

    # 检查简历是否存在
    resume = resume_service.get_by_id(resume_id)
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found"
        )

    # 检查权限
    if resume.owner_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    # 只更新提供的字段
    update_data = resume_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No update data provided"
        )

    # 更新简历
    updated_resume = resume_service.update(resume_id, update_data)
    if not updated_resume:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update resume",
        )

    return ResumeResponse.model_validate(updated_resume)


@router.delete("/{resume_id}")
async def delete_resume(
    resume_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除简历"""
    resume_service = ResumeService(db)

    # 检查简历是否存在
    resume = resume_service.get_by_id(resume_id)
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found"
        )

    # 检查权限
    if resume.owner_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    # 删除简历
    success = resume_service.delete(resume_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete resume",
        )

    return {"message": "Resume deleted successfully"}


@router.get("/{resume_id}/proposals", response_model=List[ResumeProposalResponse])
async def get_resume_proposals(
    resume_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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
    proposals = resume_service.get_proposals_by_resume(resume_id)
    return [ResumeProposalResponse.model_validate(item) for item in proposals]


@router.post("/{resume_id}/proposals/{proposal_id}/apply", response_model=ResumeProposalResponse)
async def apply_resume_proposal(
    resume_id: int,
    proposal_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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
    proposal = resume_service.get_proposal(proposal_id)
    if not proposal or proposal.resume_id != resume_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found"
        )
    applied = resume_service.apply_proposal(proposal_id)
    if not applied:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to apply proposal",
    )
    return ResumeProposalResponse.model_validate(applied)


@router.post("/{resume_id}/proposals/{proposal_id}/reject", response_model=ResumeProposalResponse)
async def reject_resume_proposal(
    resume_id: int,
    proposal_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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
    proposal = resume_service.get_proposal(proposal_id)
    if not proposal or proposal.resume_id != resume_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found"
        )
    rejected = resume_service.reject_proposal(proposal_id)
    if not rejected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reject proposal",
        )
    return ResumeProposalResponse.model_validate(rejected)


# ── 聊天记录 ──────────────────────────────────────────────────────────────────

class ChatMessageIn(BaseModel):
    role: str   # "user" | "assistant"
    content: str
    stream_events: list | None = None


class ChatMessageOut(BaseModel):
    id: int
    role: str
    content: str
    stream_events: list | None = None

    model_config = {"from_attributes": True}


def _check_resume_access(resume_id: int, user_id: int, db: Session):
    resume_service = ResumeService(db)
    resume = resume_service.get_by_id(resume_id)
    if not resume:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    if resume.owner_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    return resume


@router.get("/{resume_id}/chat-messages", response_model=List[ChatMessageOut])
async def get_chat_messages(
    resume_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取某份简历的全部聊天记录"""
    _check_resume_access(resume_id, current_user["id"], db)
    from app.models.resume import ResumeChatMessage
    msgs = (
        db.query(ResumeChatMessage)
        .filter(ResumeChatMessage.resume_id == resume_id)
        .order_by(ResumeChatMessage.id.asc())
        .all()
    )
    return [ChatMessageOut.model_validate(m) for m in msgs]


@router.post("/{resume_id}/chat-messages", response_model=List[ChatMessageOut])
async def append_chat_messages(
    resume_id: int,
    messages: List[ChatMessageIn],
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """批量追加聊天消息（一次保存用户消息 + AI 回复）"""
    _check_resume_access(resume_id, current_user["id"], db)
    from app.models.resume import ResumeChatMessage
    saved = []
    for msg in messages:
        if msg.role not in ("user", "assistant"):
            continue
        row = ResumeChatMessage(
            resume_id=resume_id,
            role=msg.role,
            content=msg.content,
            stream_events=msg.stream_events,
        )
        db.add(row)
        saved.append(row)
    db.commit()
    for row in saved:
        db.refresh(row)
    return [ChatMessageOut.model_validate(m) for m in saved]


@router.delete("/{resume_id}/chat-messages")
async def clear_chat_messages(
    resume_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """清空某份简历的聊天记录"""
    _check_resume_access(resume_id, current_user["id"], db)
    from app.models.resume import ResumeChatMessage
    db.query(ResumeChatMessage).filter(ResumeChatMessage.resume_id == resume_id).delete()
    db.commit()
    return {"message": "cleared"}
