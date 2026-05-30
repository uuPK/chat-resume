"""
认证相关数据模式

定义用户认证、注册、登录等相关的Pydantic模式。
包括请求数据验证和响应数据序列化。
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """用于校验用户注册时提交的基础字段。"""

    email: EmailStr
    password: str = Field(min_length=6)
    full_name: Optional[str] = None
    role: str = "candidate"


class UserUpdate(BaseModel):
    """用于限制当前仅允许更新的用户资料字段。"""

    full_name: Optional[str] = None


class UserResponse(BaseModel):
    """用于向前端返回安全的用户资料视图。"""

    id: int
    email: str
    full_name: Optional[str] = None
    role: str
    is_active: bool
    has_password: bool = False
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


class AuthMessageResponse(BaseModel):
    """用于返回认证流程里的通用确认消息。"""

    message: str


class ForgotPasswordRequest(BaseModel):
    """用于接收忘记密码流程提交的邮箱。"""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """用于接收密码重置token和新密码。"""

    token: str = Field(min_length=16)
    password: str = Field(min_length=6)


class ChangePasswordRequest(BaseModel):
    """用于接收已登录用户修改密码的旧密码和新密码。"""

    current_password: str = Field(min_length=6)
    new_password: str = Field(min_length=6)
