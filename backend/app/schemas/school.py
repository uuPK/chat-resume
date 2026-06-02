from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict

class MarketGapsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    top_missing_skills: list[str]
    analysis: str

class GenerateCourseRequest(BaseModel):
    target_skills: list[str]

class PublishCourseRequest(BaseModel):
    course_id: int

class AICourseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: Optional[str] = None
    target_skills: Optional[str] = None
    outline: Optional[str] = None
    published: bool
    created_at: datetime
    updated_at: datetime
