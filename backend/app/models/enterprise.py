"""
企业端数据模型

定义企业发布的岗位和求职者的投递记录。
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.infra.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.resume import Resume


class EnterpriseJob(Base):
    """用于存储企业发布的岗位信息。"""

    __tablename__ = "enterprise_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    enterprise_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    skills_required: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    salary_range: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    # Relationships
    enterprise: Mapped["User"] = relationship("User", foreign_keys=[enterprise_id])
    deliveries: Mapped[list["JobDelivery"]] = relationship("JobDelivery", back_populates="job")


class JobDelivery(Base):
    """用于存储求职者向企业岗位的投递记录。"""

    __tablename__ = "job_deliveries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("enterprise_jobs.id"), nullable=False, index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending, viewed, accepted, rejected
    match_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    analysis_result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    # Relationships
    job: Mapped["EnterpriseJob"] = relationship("EnterpriseJob", back_populates="deliveries")
    candidate: Mapped["User"] = relationship("User", foreign_keys=[candidate_id])
    resume: Mapped["Resume"] = relationship("Resume")
