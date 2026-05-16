"""
用户认证API端点模块

提供用户注册、登录、令牌刷新等认证相关的API端点。
处理用户身份验证和JWT令牌管理。
"""

import logging
from datetime import timedelta
from time import perf_counter
from typing import Literal, TypedDict, cast

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.entrypoints.http.deps import get_current_user
from app.infra.config import settings
from app.infra.database import get_db
from app.infra.security import create_access_token
from app.models.user import User
from app.schemas.auth import (
    AuthSessionResponse,
    AuthMessageResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LogoutResponse,
    RefreshTokenRequest,
    ResetPasswordRequest,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.services.auth import (
    OAuthStateService,
    PasswordResetService,
    SettingsPasswordResetMailer,
)
from app.services.auth.google_identity_link_service import (
    GoogleIdentityLinkError,
    GoogleIdentityLinkService,
)
from app.services.auth.google_oauth_client import (
    GoogleOAuthAuthenticationError,
    GoogleOAuthClient,
    GoogleOAuthConfig,
    GoogleOAuthConfigurationError,
)
from app.services.auth.oauth_state_service import OAuthStateError
from app.services.domain import RefreshSessionService, UserService

logger = logging.getLogger(__name__)

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_STR}/auth/login")
oauth_state_service = OAuthStateService()
password_reset_mailer = SettingsPasswordResetMailer()


class CookieKwargs(TypedDict, total=False):
    """用于精确定义认证 Cookie 复用参数，方便类型检查器理解展开参数。"""

    httponly: bool
    secure: bool
    samesite: Literal["lax", "strict", "none"] | None
    path: str
    domain: str


def _cookie_base_kwargs() -> CookieKwargs:
    """用于复用认证 Cookie 的公共安全参数。"""
    kwargs: CookieKwargs = {
        "httponly": True,
        "secure": settings.AUTH_COOKIE_SECURE,
        "samesite": cast(
            Literal["lax", "strict", "none"] | None,
            settings.AUTH_COOKIE_SAMESITE,
        ),
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
    user: User,
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


def _oauth_error_redirect(error_code: str) -> RedirectResponse:
    """用于把 OAuth 失败统一带回前端登录页。"""
    return RedirectResponse(
        url=f"{settings.FRONTEND_URL}/login?oauth_error={error_code}",
        status_code=status.HTTP_302_FOUND,
    )


def _build_password_reset_link(token: str) -> str:
    """用于生成前端密码重置链接。"""
    return f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?token={token}"


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


@router.post("/forgot-password", response_model=AuthMessageResponse)
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    """用于给邮箱密码用户发送密码重置链接。"""
    user_service = UserService(db)
    user = user_service.get_by_email(payload.email)
    if user and user.is_active and user.hashed_password:
        token = PasswordResetService(db).issue_token(user)
        password_reset_mailer.send_password_reset(
            email=user.email,
            reset_link=_build_password_reset_link(token),
        )
    return AuthMessageResponse(
        message="If the email exists, a password reset link has been sent."
    )


@router.post("/reset-password", response_model=AuthMessageResponse)
async def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    """用于通过一次性token设置新密码。"""
    changed = PasswordResetService(db).reset_password(
        token=payload.token,
        new_password=payload.password,
    )
    if not changed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token",
        )
    return AuthMessageResponse(message="Password has been reset.")


@router.post("/change-password", response_model=AuthMessageResponse)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于已登录邮箱密码用户修改自己的密码。"""
    changed = PasswordResetService(db).change_password(
        user_id=current_user["id"],
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    if not changed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect or password login is not enabled.",
        )
    return AuthMessageResponse(message="Password has been changed.")


@router.get("/google/login")
async def google_login():
    """用于启动 Google OAuth 授权码流程。"""
    try:
        config = GoogleOAuthConfig.from_settings(settings)
    except GoogleOAuthConfigurationError as exc:
        return _oauth_error_redirect(exc.error_code)

    state_issue = oauth_state_service.issue_state()
    authorization_url = GoogleOAuthClient(config).authorization_url(
        state=state_issue.value
    )
    return RedirectResponse(url=authorization_url, status_code=status.HTTP_302_FOUND)


@router.get("/google/callback")
async def google_callback(
    state: str | None = None,
    code: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    """用于处理 Google OAuth 回调并签发现有 Cookie 会话。"""
    try:
        oauth_state_service.consume_state(state)
    except OAuthStateError as exc:
        return _oauth_error_redirect(exc.error_code)

    if error:
        return _oauth_error_redirect("cancelled")
    if not code:
        return _oauth_error_redirect("google_exchange_failed")

    try:
        config = GoogleOAuthConfig.from_settings(settings)
        google_client = GoogleOAuthClient(config)
        tokens = await google_client.exchange_code(code)
        identity = await google_client.fetch_identity(tokens.access_token)
        user = GoogleIdentityLinkService(db).resolve_user(identity)
    except GoogleOAuthConfigurationError as exc:
        return _oauth_error_redirect(exc.error_code)
    except GoogleOAuthAuthenticationError as exc:
        return _oauth_error_redirect(exc.error_code)
    except GoogleIdentityLinkError as exc:
        return _oauth_error_redirect(exc.error_code)

    response = RedirectResponse(
        url=f"{settings.FRONTEND_URL}/dashboard",
        status_code=status.HTTP_302_FOUND,
    )
    _issue_auth_session(response, user=user, db=db)
    return response


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
    assert refresh_session is not None

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
    logger.debug(
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
