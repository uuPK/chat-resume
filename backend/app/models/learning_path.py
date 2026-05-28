"""
学习路线数据模型

定义个性化学习规划的版本控制表结构，关联到简历和面试记录。
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.infra.database import Base

if TYPE_CHECKING:
    from app.models.resume import Resume
    from app.models.interview import InterviewSession


class LearningPathVersion(Base):
    __tablename__ = "learning_path_versions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    resume_id: Mapped[int] = mapped_column(
        ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    interview_session_id: Mapped[int | None] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    
    # 触发类型: "resume_update", "interview_completed", "manual"
    trigger_type: Mapped[str] = mapped_column(String, nullable=False)
    
    # LLM 生成的规划数据 (包含阶段目标、周任务等)
    plan_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    resume: Mapped["Resume"] = relationship("Resume")
    interview_session: Mapped["InterviewSession"] = relationship("InterviewSession")
