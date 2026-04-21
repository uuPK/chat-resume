"""
简历数据模型

定义简历相关的数据库表结构，包括简历内容、优化记录和聊天记录等。
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.infra.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    layout_config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String, nullable=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    # Relationships
    owner: Mapped["User"] = relationship("User", back_populates="resumes")
    optimization_records: Mapped[list["OptimizationRecord"]] = relationship(
        "OptimizationRecord", back_populates="resume"
    )
    chat_messages: Mapped[list["ResumeChatMessage"]] = relationship(
        "ResumeChatMessage", back_populates="resume", order_by="ResumeChatMessage.id"
    )


class OptimizationRecord(Base):
    __tablename__ = "optimization_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id"), nullable=False)
    jd_content: Mapped[str] = mapped_column(Text, nullable=False)
    suggestions: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    applied: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    resume: Mapped["Resume"] = relationship(
        "Resume", back_populates="optimization_records"
    )


class ResumeChatMessage(Base):
    __tablename__ = "resume_chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id"), nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    stream_events: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON, nullable=True
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    resume: Mapped["Resume"] = relationship("Resume", back_populates="chat_messages")
