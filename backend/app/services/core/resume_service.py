"""
简历业务逻辑服务模块

提供简历相关的核心业务逻辑，包括简历的创建、更新、查询、删除等操作。
处理简历数据验证和业务规则。
"""

from sqlalchemy.orm.attributes import flag_modified
from typing import List
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.resume import Resume, OptimizationRecord, InterviewSession, ResumeProposal
from app.schemas.resume import ResumeCreate, ResumeContent, dump_resume_content_for_frontend
from .file_service import FileService
import logging

logger = logging.getLogger(__name__)


class ResumeService:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, resume_id: int) -> Resume:
        return self.db.query(Resume).filter(Resume.id == resume_id).first()

    def get_by_owner(self, owner_id: int) -> List[Resume]:
        return self.db.query(Resume).filter(Resume.owner_id == owner_id).all()

    def create(self, resume_create: ResumeCreate, owner_id: int) -> Resume:
        """创建简历记录"""
        resume = Resume(
            title=resume_create.title,
            content=self._serialize_content(resume_create.content),
            original_filename=resume_create.original_filename,
            owner_id=owner_id,
        )

        try:
            self.db.add(resume)
            self.db.commit()
            self.db.refresh(resume)
            return resume
        except Exception as e:
            # 回滚事务
            self.db.rollback()
            # 记录错误日志
            logger.error(f"简历创建失败: {str(e)}")
            # 重新抛出异常供上层处理
            raise e

    def update(self, resume_id: int, resume_update: dict) -> Resume:
        resume = self.get_by_id(resume_id)
        if resume:
            for key, value in resume_update.items():
                if key == "content":
                    value = self._serialize_content(value)
                setattr(resume, key, value)
                if key == "content":
                    flag_modified(resume, "content")
            self.db.commit()
            self.db.refresh(resume)
        return resume

    def _serialize_content(self, content: ResumeContent | dict) -> dict:
        """统一将简历内容转换为稳定的 JSON 文档结构。"""
        return dump_resume_content_for_frontend(content)

    def delete(self, resume_id: int) -> bool:
        """删除简历及其关联数据"""
        # 获取要删除的简历
        resume = self.get_by_id(resume_id)
        if not resume:
            return False

        try:
            # 删除关联的优化记录
            self.db.query(OptimizationRecord).filter(
                OptimizationRecord.resume_id == resume_id
            ).delete()

            # 删除关联的面试会话
            self.db.query(InterviewSession).filter(
                InterviewSession.resume_id == resume_id
            ).delete()

            self.db.query(ResumeProposal).filter(
                ResumeProposal.resume_id == resume_id
            ).delete()

            # 删除关联的文件
            if resume.file_path is not None:
                file_service = FileService()
                file_service.delete_file(str(resume.file_path))

            # 删除简历记录
            self.db.delete(resume)
            self.db.commit()

            return True

        except Exception:
            # 回滚事务
            self.db.rollback()
            return False

    def create_proposal(
        self,
        resume_id: int,
        user_message: str,
        proposed_content: dict,
        summary: str | None = None,
        section: str | None = None,
        proposed_patch: dict | None = None,
        tool_calls: list[dict] | None = None,
    ) -> ResumeProposal:
        proposal = ResumeProposal(
            resume_id=resume_id,
            user_message=user_message,
            section=section,
            summary=summary,
            proposed_content=self._serialize_content(proposed_content),
            proposed_patch=proposed_patch,
            tool_calls=tool_calls,
            status="pending",
        )
        self.db.add(proposal)
        self.db.commit()
        self.db.refresh(proposal)
        return proposal

    def get_proposal(self, proposal_id: int) -> ResumeProposal | None:
        return self.db.query(ResumeProposal).filter(ResumeProposal.id == proposal_id).first()

    def get_proposals_by_resume(self, resume_id: int) -> List[ResumeProposal]:
        return (
            self.db.query(ResumeProposal)
            .filter(ResumeProposal.resume_id == resume_id)
            .order_by(ResumeProposal.id.desc())
            .all()
        )

    def apply_proposal(self, proposal_id: int) -> ResumeProposal | None:
        proposal = self.get_proposal(proposal_id)
        if not proposal:
            return None
        resume = self.get_by_id(proposal.resume_id)
        if not resume:
            return None
        resume.content = self._serialize_content(proposal.proposed_content)
        flag_modified(resume, "content")
        proposal.status = "applied"
        proposal.applied_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(proposal)
        return proposal

    def reject_proposal(self, proposal_id: int) -> ResumeProposal | None:
        proposal = self.get_proposal(proposal_id)
        if not proposal:
            return None
        proposal.status = "rejected"
        self.db.commit()
        self.db.refresh(proposal)
        return proposal
