"""
认证相关数据模式

定义用户认证、注册、登录等相关的Pydantic模式。
包括请求数据验证和响应数据序列化。
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """用于校验用户注册时提交的基础字段。"""

    email: EmailStr
    password: str = Field(min_length=6)
    full_name: Optional[str] = None


class UserUpdate(BaseModel):
    """用于限制当前仅允许更新的用户资料字段。"""

    full_name: Optional[str] = None


class UserResponse(BaseModel):
    """用于向前端返回安全的用户资料视图。"""

    id: int
    email: str
    full_name: Optional[str] = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    """用于兼容旧接口保留的令牌响应结构。"""

    access_token: str
    token_type: str


class AuthSessionResponse(BaseModel):
    """用于返回已建立登录态后的用户信息。"""

    token_type: str
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    """用于兼容旧客户端显式传入刷新令牌。"""

    refresh_token: str


class LogoutResponse(BaseModel):
    """用于返回登出后的确认信息。"""

    message: str
