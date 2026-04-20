"""
安全认证模块

负责JWT令牌的创建和验证，密码哈希和验证等安全相关功能。
提供用户认证和授权的安全保障。
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Union
from urllib.parse import urlencode

from jose import jwt
from passlib.context import CryptContext

from app.infra.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"


def create_access_token(
    subject: Union[str, Any], expires_delta: timedelta | None = None
) -> str:
    """用于签发短期访问令牌给后续 API 鉴权使用。"""
    return create_token(
        subject=subject, expires_delta=expires_delta, token_type="access"
    )


def create_refresh_token(
    subject: Union[str, Any], expires_delta: timedelta | None = None
) -> str:
    """用于兼容旧流程生成刷新令牌。"""
    return create_token(
        subject=subject, expires_delta=expires_delta, token_type="refresh"
    )


def create_token(
    subject: Union[str, Any],
    expires_delta: timedelta | None = None,
    token_type: str = "access",
) -> str:
    """用于复用统一的 JWT 编码逻辑。"""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode = {"exp": expire, "sub": str(subject), "type": token_type}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict[str, Any]:
    """用于解析 JWT 并返回其中的声明。"""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])


def generate_session_token() -> str:
    """用于生成只在服务端可校验的高熵会话令牌。"""
    return secrets.token_urlsafe(48)


def hash_session_token(token: str) -> str:
    """用于把原始会话令牌转成可持久化存储的固定摘要。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_download_token(
    *, filename: str, user_id: int, expires_in_seconds: int = 300
) -> str:
    """用于给受保护下载链接签发短时校验参数。"""
    expires_at = int(
        (datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)).timestamp()
    )
    payload = f"{filename}:{user_id}:{expires_at}"
    signature = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return urlencode(
        {
            "expires": str(expires_at),
            "user_id": str(user_id),
            "signature": signature,
        }
    )


def verify_download_token(
    *, filename: str, user_id: int, expires: int, signature: str
) -> bool:
    """用于校验下载链接里的签名参数是否仍然有效。"""
    if expires < int(datetime.now(timezone.utc).timestamp()):
        return False

    payload = f"{filename}:{user_id}:{expires}"
    expected = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """用于验证明文密码和数据库哈希是否匹配。"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """用于把用户密码安全地转成 bcrypt 哈希。"""
    return pwd_context.hash(password)
