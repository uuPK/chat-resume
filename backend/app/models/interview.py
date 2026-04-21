"""
面试数据模型

定义结构化面试 session / turn / report 的最小表结构。
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


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    resume_id: Mapped[int] = mapped_column(
        ForeignKey("resumes.id"), nullable=False, index=True
    )
    target_title: Mapped[str | None] = mapped_column(String, nullable=True)
    target_company: Mapped[str | None] = mapped_column(String, nullable=True)
    jd_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    interview_type: Mapped[str] = mapped_column(
        String, nullable=False, default="general"
    )
    difficulty: Mapped[str] = mapped_column(String, nullable=False, default="medium")
    language: Mapped[str] = mapped_column(String, nullable=False, default="zh-CN")
    mode: Mapped[str] = mapped_column(String, nullable=False, default="practice")
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="created", index=True
    )
    current_round_index: Mapped[int] = mapped_column(nullable=False, default=0)
    current_turn_index: Mapped[int] = mapped_column(nullable=False, default=0)
    plan_json: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        JSON, nullable=True
    )
    report_data: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        JSON, nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    resume: Mapped["Resume"] = relationship("Resume")
    turns: Mapped[list["InterviewTurn"]] = relationship(
        "InterviewTurn",
        back_populates="session",
        order_by="InterviewTurn.turn_index",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class InterviewTurn(Base):
    __tablename__ = "interview_turns"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("interview_sessions.id"), nullable=False, index=True
    )
    turn_index: Mapped[int] = mapped_column(nullable=False)
    round_index: Mapped[int] = mapped_column(nullable=False, default=0)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[str] = mapped_column(
        String, nullable=False, default="general"
    )
    intent: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_points: Mapped[list[Any] | dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    evaluation: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    follow_up_count: Mapped[int] = mapped_column(nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="planned", index=True
    )
    asked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    answered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    session: Mapped["InterviewSession"] = relationship(
        "InterviewSession", back_populates="turns"
    )
