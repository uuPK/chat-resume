"""
API依赖项模块

提供FastAPI路由的依赖注入功能，包括数据库会话、用户认证、权限验证等。
确保API端点的安全性和数据一致性。
"""

import logging
from time import perf_counter
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session
from app.infra.config import settings
from app.infra.database import get_db
from app.infra.security import decode_access_token
from app.services.domain import UserService

# 这里关闭自动报错，方便中间件和依赖统一复用同一套鉴权逻辑。
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_STR}/auth/login",
    auto_error=False,
)
logger = logging.getLogger(__name__)


def _credentials_exception() -> HTTPException:
    """用于统一构造认证失败时的异常响应。"""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _get_request_token(request: Request, bearer_token: str | None) -> str | None:
    """用于统一从请求头或 HttpOnly Cookie 中提取访问令牌。"""
    if bearer_token:
        return bearer_token
    return request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)


def _decode_token_claims(token: str) -> dict:
    """用于解析访问令牌并提取最小用户声明。"""
    try:
        payload = decode_access_token(token)
        user_id_str = payload.get("sub")
        if user_id_str is None:
            raise _credentials_exception()
        user_id = int(user_id_str)
    except (JWTError, ValueError, TypeError):
        raise _credentials_exception()
    return {"id": user_id, **payload}


def _build_current_user_payload(user: Any) -> dict[str, Any]:
    """用于把数据库用户对象裁剪成请求上下文所需字段。"""
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "is_active": user.is_active,
        "created_at": user.created_at,
    }


def authenticate_token_with_db(token: str, db: Session) -> tuple[dict[str, Any], dict[str, Any]]:
    """用于给中间件和依赖复用完整的令牌鉴权流程。"""
    claims = _decode_token_claims(token)
    user_service = UserService(db)
    user = user_service.get_by_id(claims["id"])
    if user is None:
        raise _credentials_exception()
    if not user.is_active:
        raise _credentials_exception()
    return claims, _build_current_user_payload(user)


def _get_cached_request_value(request: Request, key: str) -> Any:
    """用于优先复用中间件已写入请求上下文的认证结果。"""
    return getattr(request.state, key, None)


async def get_current_user_claims(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
):
    """用于在只需声明信息时避免额外查询用户表。"""
    cached_claims = _get_cached_request_value(request, "current_user_claims")
    if cached_claims is not None:
        return cached_claims
    resolved_token = _get_request_token(request, token)
    if not resolved_token:
        raise _credentials_exception()

    started_at = perf_counter()
    decode_started_at = perf_counter()
    claims = _decode_token_claims(resolved_token)
    request.state.current_user_claims = claims
    decode_elapsed_ms = (perf_counter() - decode_started_at) * 1000
    total_elapsed_ms = (perf_counter() - started_at) * 1000
    logger.info(
        "get_current_user_claims timings user_id=%s decode_ms=%.2f total_ms=%.2f",
        claims["id"],
        decode_elapsed_ms,
        total_elapsed_ms,
    )
    return claims


async def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    """用于解析令牌并返回数据库中的当前用户信息。"""
    cached_user = _get_cached_request_value(request, "current_user")
    if cached_user is not None:
        return cached_user
    resolved_token = _get_request_token(request, token)
    if not resolved_token:
        raise _credentials_exception()

    started_at = perf_counter()
    cached_claims = _get_cached_request_value(request, "current_user_claims")
    decode_elapsed_ms = 0.0
    query_started_at = perf_counter()
    if cached_claims is not None:
        user_id = cached_claims["id"]
        user_service = UserService(db)
        user = user_service.get_by_id(user_id)
        if user is None:
            raise _credentials_exception()
        current_user = _build_current_user_payload(user)
    else:
        decode_started_at = perf_counter()
        claims, current_user = authenticate_token_with_db(resolved_token, db)
        request.state.current_user_claims = claims
        decode_elapsed_ms = (perf_counter() - decode_started_at) * 1000
        user_id = claims["id"]
    query_elapsed_ms = (perf_counter() - query_started_at) * 1000
    request.state.current_user = current_user

    total_elapsed_ms = (perf_counter() - started_at) * 1000
    logger.info(
        "get_current_user timings user_id=%s decode_ms=%.2f query_ms=%.2f total_ms=%.2f",
        user_id,
        decode_elapsed_ms,
        query_elapsed_ms,
        total_elapsed_ms,
    )

    return current_user
