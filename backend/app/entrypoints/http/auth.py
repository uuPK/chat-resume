"""
用户认证API端点模块

提供用户注册、登录、令牌刷新等认证相关的API端点。
处理用户身份验证和JWT令牌管理。
"""

import logging
from datetime import timedelta
from time import perf_counter

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.entrypoints.http.deps import get_current_user
from app.infra.config import settings
from app.infra.database import get_db
from app.infra.security import create_access_token
from app.schemas.auth import (
    AuthSessionResponse,
    LogoutResponse,
    RefreshTokenRequest,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.services.domain import RefreshSessionService, UserService

logger = logging.getLogger(__name__)

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_STR}/auth/login")


def _cookie_base_kwargs() -> dict[str, object]:
    """用于复用认证 Cookie 的公共安全参数。"""
    kwargs: dict[str, object] = {
        "httponly": True,
        "secure": settings.AUTH_COOKIE_SECURE,
        "samesite": settings.AUTH_COOKIE_SAMESITE,
        "path": "/",
    }
    if settings.AUTH_COOKIE_DOMAIN.strip():
        kwargs["domain"] = settings.AUTH_COOKIE_DOMAIN.strip()
    return kwargs


def _set_auth_cookies(
    response: Response,
    *,
    access_token: str,
    refresh_token: str,
) -> None:
    """用于把新的访问令牌和刷新令牌写入 HttpOnly Cookie。"""
    cookie_kwargs = _cookie_base_kwargs()
    response.set_cookie(
        settings.ACCESS_TOKEN_COOKIE_NAME,
        access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        **cookie_kwargs,
    )
    response.set_cookie(
        settings.REFRESH_TOKEN_COOKIE_NAME,
        refresh_token,
        max_age=settings.REFRESH_SESSION_EXPIRE_DAYS * 24 * 60 * 60,
        **cookie_kwargs,
    )


def _clear_auth_cookies(response: Response) -> None:
    """用于在登出或认证失效时清理浏览器中的认证 Cookie。"""
    cookie_kwargs = _cookie_base_kwargs()
    response.delete_cookie(settings.ACCESS_TOKEN_COOKIE_NAME, **cookie_kwargs)
    response.delete_cookie(settings.REFRESH_TOKEN_COOKIE_NAME, **cookie_kwargs)


def _issue_auth_session(
    response: Response,
    *,
    user,
    db: Session,
    previous_session_token: str | None = None,
) -> AuthSessionResponse:
    """用于签发访问令牌并轮换服务端刷新会话。"""
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.id, expires_delta=access_token_expires
    )

    refresh_session_service = RefreshSessionService(db)
    session, refresh_token = refresh_session_service.create_session(user.id)
    if previous_session_token:
        previous_session = refresh_session_service.get_session_by_token(
            previous_session_token
        )
        if previous_session and previous_session.id != session.id:
            refresh_session_service.revoke_session(
                previous_session,
                replaced_by_session_id=session.id,
            )

    _set_auth_cookies(
        response,
        access_token=access_token,
        refresh_token=refresh_token,
    )
    return AuthSessionResponse.model_validate(
        {
            "token_type": "bearer",
            "user": user,
        }
    )


def _get_refresh_token_from_request(
    request: Request,
    payload: RefreshTokenRequest | None,
) -> str | None:
    """用于兼容 Cookie 和旧 body 两种刷新令牌来源。"""
    cookie_token = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    if cookie_token:
        return cookie_token
    if payload is not None:
        return payload.refresh_token
    return None


@router.post("/register", response_model=UserResponse)
async def register(user_create: UserCreate, db: Session = Depends(get_db)):
    """用于创建新用户账号并阻止重复邮箱注册。"""
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


@router.post("/login", response_model=AuthSessionResponse)
async def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """用于校验邮箱密码并签发访问令牌。"""
    user_service = UserService(db)

    # 验证用户
    user = user_service.authenticate(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return _issue_auth_session(response, user=user, db=db)


@router.post("/refresh", response_model=AuthSessionResponse)
async def refresh_token(
    response: Response,
    request: Request,
    payload: RefreshTokenRequest | None = Body(default=None),
    db: Session = Depends(get_db),
):
    """用于用刷新令牌换发一组新的登录令牌。"""
    refresh_token_value = _get_refresh_token_from_request(request, payload)
    if not refresh_token_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    refresh_session_service = RefreshSessionService(db)
    refresh_session = refresh_session_service.get_session_by_token(refresh_token_value)
    if not refresh_session_service.is_session_active(refresh_session):
        _clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    user_service = UserService(db)
    user = user_service.get_by_id(int(refresh_session.user_id))
    if not user or not user.is_active:
        _clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    refresh_session_service.touch_session(refresh_session)
    return _issue_auth_session(
        response,
        user=user,
        db=db,
        previous_session_token=refresh_token_value,
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    """用于吊销当前刷新会话并清理浏览器登录 Cookie。"""
    refresh_token_value = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    if refresh_token_value:
        refresh_session_service = RefreshSessionService(db)
        refresh_session = refresh_session_service.get_session_by_token(
            refresh_token_value
        )
        if refresh_session and refresh_session.revoked_at is None:
            refresh_session_service.revoke_session(refresh_session)
    _clear_auth_cookies(response)
    return LogoutResponse(message="Logged out")


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """用于返回当前登录用户的基础信息。"""
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
    """用于更新当前登录用户的可编辑资料。"""
    logger.info(
        "更新用户信息请求 - 用户ID: %s, 更新数据: %s",
        current_user["id"],
        user_update.model_dump(),
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
        "用户信息更新成功 - 用户ID: %s, 新姓名: %s",
        updated_user.id,
        updated_user.full_name,
    )

    return UserResponse.model_validate(updated_user)
