"""用于定义 Agent 会话和事件日志的持久化模型。"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.infra.database import Base


class AgentSession(Base):
    """用于保存一次 Agent 执行的总体状态。"""

    __tablename__ = "agent_sessions"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id"), nullable=True, index=True)
    task_type = Column(String, nullable=False)
    status = Column(String, nullable=False, default="created", index=True)
    current_step = Column(String, nullable=True)
    failed_reason = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    events = relationship(
        "AgentEvent",
        back_populates="session",
        order_by="AgentEvent.sequence",
        cascade="all, delete-orphan",
    )


class AgentEvent(Base):
    """用于保存会话执行过程中的有序事件。"""

    __tablename__ = "agent_events"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("agent_sessions.id"), nullable=False, index=True)
    sequence = Column(Integer, nullable=False)
    event_type = Column(String, nullable=False, index=True)
    source = Column(String, nullable=False)
    payload = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("AgentSession", back_populates="events")


__all__ = ["AgentEvent", "AgentSession"]
