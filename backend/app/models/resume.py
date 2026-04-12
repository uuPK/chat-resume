"""
简历数据模型

定义简历相关的数据库表结构，包括简历内容、优化记录和提案等。
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.infra.database import Base


class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    content = Column(JSON, nullable=False)  # 结构化简历内容
    original_filename = Column(String, nullable=True)
    file_path = Column(String, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    owner = relationship("User", back_populates="resumes")
    optimization_records = relationship("OptimizationRecord", back_populates="resume")
    proposals = relationship("ResumeProposal", back_populates="resume")
    chat_messages = relationship("ResumeChatMessage", back_populates="resume", order_by="ResumeChatMessage.id")


class OptimizationRecord(Base):
    __tablename__ = "optimization_records"

    id = Column(Integer, primary_key=True, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id"), nullable=False)
    jd_content = Column(Text, nullable=False)
    suggestions = Column(JSON, nullable=False)
    applied = Column(JSON, nullable=True)  # 用户应用的建议
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    resume = relationship("Resume", back_populates="optimization_records")


class ResumeProposal(Base):
    __tablename__ = "resume_proposals"

    id = Column(Integer, primary_key=True, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id"), nullable=False)
    user_message = Column(Text, nullable=False)
    section = Column(String, nullable=True)
    status = Column(String, nullable=False, default="pending")  # pending, applied, rejected
    summary = Column(Text, nullable=True)
    proposed_content = Column(JSON, nullable=False)
    proposed_patch = Column(JSON, nullable=True)
    tool_calls = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    applied_at = Column(DateTime(timezone=True), nullable=True)

    resume = relationship("Resume", back_populates="proposals")


class ResumeChatMessage(Base):
    __tablename__ = "resume_chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id"), nullable=False)
    role = Column(String, nullable=False)   # "user" | "assistant"
    content = Column(Text, nullable=False)
    stream_events = Column(JSON, nullable=True)  # 工具确认事件流（confirmed/rejected + diffSummary）
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    resume = relationship("Resume", back_populates="chat_messages")
