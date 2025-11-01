"""
简历相关数据模式

定义简历创建、更新、查询等相关的Pydantic模式。
包括简历内容验证和API数据交换格式。
"""

from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel


class ResumeCreate(BaseModel):
    model_config = {"from_attributes": True}

    title: str
    content: Dict[str, Any]
    original_filename: Optional[str] = None


class ResumeUpdate(BaseModel):
    model_config = {"from_attributes": True}

    title: Optional[str] = None
    content: Optional[Dict[str, Any]] = None
    original_filename: Optional[str] = None


class ResumeResponse(BaseModel):
    id: int
    title: str
    content: Dict[str, Any]
    original_filename: Optional[str] = None
    owner_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class OptimizationRequest(BaseModel):
    model_config = {"from_attributes": True}

    jd_content: str


class OptimizationResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    resume_id: int
    jd_content: str
    suggestions: Dict[str, Any]
    created_at: datetime
