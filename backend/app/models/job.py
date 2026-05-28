"""
职位匹配数据模型

定义职位推荐和匹配度报告的数据库表结构。
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


class JobRecommendation(Base):
    """用于存储基于简历生成的推荐职位列表。"""
    
    __tablename__ = "job_recommendations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id"), nullable=False)
    recommendations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    resume: Mapped["Resume"] = relationship("Resume")


class JobMatchReport(Base):
    """用于存储简历与特定目标JD的深度匹配分析报告。"""
    
    __tablename__ = "job_match_reports"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id"), nullable=False)
    target_jd: Mapped[str] = mapped_column(Text, nullable=False)
    analysis_result: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    resume: Mapped["Resume"] = relationship("Resume")
