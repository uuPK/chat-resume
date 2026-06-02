from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from app.infra.database import Base

class CandidateCourseEnrollment(Base):
    __tablename__ = "candidate_course_enrollments"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    course_id = Column(Integer, ForeignKey("ai_courses.id"), index=True, nullable=False)
    status = Column(String(50), default="in_progress") # in_progress, completed
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
