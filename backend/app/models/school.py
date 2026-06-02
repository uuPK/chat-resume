from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app.infra.database import Base


class AICourse(Base):
    __tablename__ = "ai_courses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    target_skills = Column(Text, nullable=True)  # Comma-separated list of skills, or JSON
    outline = Column(Text, nullable=True)        # JSON string containing the course outline/weeks
    published = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
