"""
简历业务逻辑服务模块

提供简历相关的核心业务逻辑，包括简历的创建、更新、查询、删除等操作。
处理简历数据验证和业务规则。
"""

import logging
from typing import List

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.resume import OptimizationRecord, Resume
from app.schemas.resume import (
    ResumeContent,
    ResumeCreate,
    dump_resume_content_for_frontend,
)

from .file_service import FileService

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
            self.db.rollback()
            logger.error(f"简历创建失败: {str(e)}")
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
        resume = self.get_by_id(resume_id)
        if not resume:
            return False

        try:
            self.db.query(OptimizationRecord).filter(
                OptimizationRecord.resume_id == resume_id
            ).delete()

            if resume.file_path is not None:
                file_service = FileService()
                file_service.delete_file(str(resume.file_path))

            self.db.delete(resume)
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            return False
