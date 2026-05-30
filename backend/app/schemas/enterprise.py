"""企业端数据校验模型"""

from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, Field

class EnterpriseJobCreate(BaseModel):
    title: str = Field(..., example="Frontend Engineer")
    description: str = Field(..., example="We are looking for a Next.js expert...")
    skills_required: List[str] = Field(default_factory=list, example=["React", "TypeScript"])
    location: Optional[str] = None
    salary_range: Optional[str] = None

class EnterpriseJobUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    skills_required: Optional[List[str]] = None
    location: Optional[str] = None
    salary_range: Optional[str] = None
    is_active: Optional[bool] = None

class EnterpriseJobResponse(BaseModel):
    id: int
    enterprise_id: int
    title: str
    description: str
    skills_required: List[str]
    location: Optional[str] = None
    salary_range: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class JobDeliveryCreate(BaseModel):
    job_id: int

class JobDeliveryResponse(BaseModel):
    id: int
    job_id: int
    candidate_id: int
    resume_id: int
    status: str
    match_score: Optional[int] = None
    analysis_result: Optional[dict] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class DeliveryWithDetailsResponse(JobDeliveryResponse):
    candidate_name: str
    resume_title: str
    job_title: str

class MatchAnalysisRequest(BaseModel):
    delivery_id: int
