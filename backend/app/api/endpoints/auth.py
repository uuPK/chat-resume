"""
用户认证API端点模块

提供用户注册、登录、令牌刷新等认证相关的API端点。
处理用户身份验证和JWT令牌管理。
"""

from datetime import timedelta
from time import perf_counter
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.infra.database import get_db
from app.infra.security import create_access_token, create_refresh_token, decode_access_token
from app.infra.config import settings
from app.schemas.auth import (
    UserCreate,
    UserUpdate,
    UserResponse,
    LoginResponse,
    RefreshTokenRequest,
)
from app.services.domain import UserService
from app.api.deps import get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_STR}/auth/login")


@router.post("/register", response_model=UserResponse)
async def register(user_create: UserCreate, db: Session = Depends(get_db)):
    logger.info(f"Register endpoint called with email: {user_create.email}")
    user_service = UserService(db)

    # 检查用户是否已存在
    existing_user = user_service.get_by_email(user_create.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    # 创建用户
    user = user_service.create(user_create)
    return UserResponse.model_validate(user)


@router.post("/login", response_model=LoginResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    user_service = UserService(db)

    # 验证用户
    user = user_service.authenticate(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 创建访问令牌
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.id, expires_delta=access_token_expires
    )
    refresh_token = create_refresh_token(subject=user.id, expires_delta=timedelta(days=30))

    # 返回包含用户信息的响应
    return LoginResponse.model_validate(
        {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": user,
        }
    )


@router.post("/refresh", response_model=LoginResponse)
async def refresh_token(
    request: RefreshTokenRequest, db: Session = Depends(get_db)
):
    try:
        claims = decode_access_token(request.refresh_token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    if claims.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    user_service = UserService(db)
    user = user_service.get_by_id(int(claims["sub"]))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    access_token = create_access_token(
        subject=user.id,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh_token_value = create_refresh_token(
        subject=user.id,
        expires_delta=timedelta(days=30),
    )
    return LoginResponse.model_validate(
        {
            "access_token": access_token,
            "refresh_token": refresh_token_value,
            "token_type": "bearer",
            "user": user,
        }
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """获取当前用户信息"""
    started_at = perf_counter()
    response = UserResponse.model_validate(current_user)
    total_elapsed_ms = (perf_counter() - started_at) * 1000
    logger.info(
        "auth.me timings user_id=%s model_validate_ms=%.2f",
        current_user["id"],
        total_elapsed_ms,
    )
    return response


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新当前用户信息"""
    logger.info(
        f"更新用户信息请求 - 用户ID: {current_user['id']}, 更新数据: {user_update.model_dump()}"
    )
    user_service = UserService(db)

    # 更新用户信息
    updated_user = user_service.update(current_user["id"], user_update)
    if not updated_user:
        logger.error(f"用户不存在: {current_user['id']}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    logger.info(
        f"用户信息更新成功 - 用户ID: {updated_user.id}, 新姓名: {updated_user.full_name}"
    )

    return UserResponse.model_validate(updated_user)
