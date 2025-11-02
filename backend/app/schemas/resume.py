"""
简历相关数据模式

定义简历创建、更新、查询等相关的Pydantic模式。
包括简历内容验证和API数据交换格式。
"""

from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel


class ResumeCreate(BaseModel):
    """简历创建模式

    用于创建新简历时的数据验证，包含简历标题、内容和原始文件名。
    """
    model_config = {"from_attributes": True}

    title: str
    content: Dict[str, Any]
    original_filename: Optional[str] = None


class ResumeUpdate(BaseModel):
    """简历更新模式

    用于更新现有简历时的数据验证，所有字段都是可选的。
    """
    model_config = {"from_attributes": True}

    title: Optional[str] = None
    content: Optional[Dict[str, Any]] = None
    original_filename: Optional[str] = None


class ResumeResponse(BaseModel):
    """简历响应模式

    用于API返回简历数据，包含完整的简历信息和时间戳。
    """
    id: int
    title: str
    content: Dict[str, Any]
    original_filename: Optional[str] = None
    owner_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class OptimizationRequest(BaseModel):
    """简历优化请求模式

    用于提交简历优化请求，包含职位描述内容。
    """
    model_config = {"from_attributes": True}

    jd_content: str


class OptimizationResponse(BaseModel):
    """简历优化响应模式

    用于返回简历优化结果，包含优化建议和相关信息。
    """
    model_config = {"from_attributes": True}

    id: int
    resume_id: int
    jd_content: str
    suggestions: Dict[str, Any]
    created_at: datetime
