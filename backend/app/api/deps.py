"""
API依赖项模块

提供FastAPI路由的依赖注入功能，包括数据库会话、用户认证、权限验证等。
确保API端点的安全性和数据一致性。
"""

import logging
from time import perf_counter

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session
from app.infra.config import settings
from app.infra.database import get_db
from app.infra.security import decode_access_token
from app.services.domain import UserService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_STR}/auth/login")
logger = logging.getLogger(__name__)


def _decode_token_claims(token: str) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
        user_id_str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        user_id = int(user_id_str)
    except (JWTError, ValueError, TypeError):
        raise credentials_exception
    return {"id": user_id, **payload}


async def get_current_user_claims(token: str = Depends(oauth2_scheme)):
    started_at = perf_counter()
    decode_started_at = perf_counter()
    claims = _decode_token_claims(token)
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
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
):
    started_at = perf_counter()
    decode_started_at = perf_counter()
    claims = _decode_token_claims(token)
    decode_elapsed_ms = (perf_counter() - decode_started_at) * 1000
    user_id = claims["id"]

    user_service = UserService(db)
    query_started_at = perf_counter()
    user = user_service.get_by_id(user_id)
    query_elapsed_ms = (perf_counter() - query_started_at) * 1000
    if user is None:
        raise credentials_exception

    total_elapsed_ms = (perf_counter() - started_at) * 1000
    logger.info(
        "get_current_user timings user_id=%s decode_ms=%.2f query_ms=%.2f total_ms=%.2f",
        user_id,
        decode_elapsed_ms,
        query_elapsed_ms,
        total_elapsed_ms,
    )

    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "is_active": user.is_active,
        "created_at": user.created_at,
    }
