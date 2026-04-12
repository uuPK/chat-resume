"""
面试数据模型

定义结构化面试 session / turn / report 的最小表结构。
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.infra.database import Base


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id"), nullable=False, index=True)
    target_title = Column(String, nullable=True)
    target_company = Column(String, nullable=True)
    jd_text = Column(Text, nullable=True)
    interview_type = Column(String, nullable=False, default="general")
    difficulty = Column(String, nullable=False, default="medium")
    language = Column(String, nullable=False, default="zh-CN")
    mode = Column(String, nullable=False, default="text")
    status = Column(String, nullable=False, default="created", index=True)
    current_round_index = Column(Integer, nullable=False, default=0)
    current_turn_index = Column(Integer, nullable=False, default=0)
    plan_json = Column(JSON, nullable=True)
    overall_score = Column(Integer, nullable=True)
    report_data = Column(JSON, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    resume = relationship("Resume")
    turns = relationship(
        "InterviewTurn",
        back_populates="session",
        order_by="InterviewTurn.turn_index",
        cascade="all, delete-orphan",
    )


class InterviewTurn(Base):
    __tablename__ = "interview_turns"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("interview_sessions.id"), nullable=False, index=True)
    turn_index = Column(Integer, nullable=False)
    round_index = Column(Integer, nullable=False, default=0)
    question = Column(Text, nullable=False)
    question_type = Column(String, nullable=False, default="general")
    intent = Column(Text, nullable=True)
    expected_points = Column(JSON, nullable=True)
    answer = Column(Text, nullable=True)
    evaluation = Column(JSON, nullable=True)
    score = Column(Integer, nullable=True)
    follow_up_count = Column(Integer, nullable=False, default=0)
    status = Column(String, nullable=False, default="planned", index=True)
    asked_at = Column(DateTime(timezone=True), nullable=True)
    answered_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    session = relationship("InterviewSession", back_populates="turns")
