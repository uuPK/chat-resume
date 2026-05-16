"""用于管理密码重置令牌和密码变更。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.infra.config import settings
from app.infra.security import (
    generate_session_token,
    get_password_hash,
    hash_session_token,
    verify_password,
)
from app.models.user import PasswordResetToken, User


class PasswordResetService:
    """用于封装忘记密码、重置密码和修改密码逻辑。"""

    def __init__(self, db: Session):
        """用于保存当前请求复用的数据库会话。"""
        self.db = db

    def issue_token(self, user: User) -> str:
        """用于为邮箱密码用户创建一次性重置token。"""
        token = generate_session_token()
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
        )
        self.db.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=hash_session_token(token),
                expires_at=expires_at,
            )
        )
        self.db.commit()
        return token

    def reset_password(self, *, token: str, new_password: str) -> bool:
        """用于校验一次性token并替换用户密码。"""
        reset_token = self._get_active_token(token)
        if reset_token is None:
            return False
        user = self.db.query(User).filter(User.id == reset_token.user_id).first()
        if user is None or not user.is_active:
            return False
        user.hashed_password = get_password_hash(new_password)
        reset_token.used_at = datetime.now(timezone.utc)
        self.db.commit()
        return True

    def change_password(
        self,
        *,
        user_id: int,
        current_password: str,
        new_password: str,
    ) -> bool:
        """用于已登录邮箱密码用户修改自己的密码。"""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not self._can_change_password(user, current_password):
            return False
        assert user is not None
        user.hashed_password = get_password_hash(new_password)
        self.db.commit()
        return True

    def _get_active_token(self, token: str) -> PasswordResetToken | None:
        """用于按原始token查找仍可使用的记录。"""
        token_hash = hash_session_token(token)
        reset_token = (
            self.db.query(PasswordResetToken)
            .filter(PasswordResetToken.token_hash == token_hash)
            .first()
        )
        if reset_token is None or reset_token.used_at is not None:
            return None
        if self._is_expired(reset_token.expires_at):
            return None
        return reset_token

    def _is_expired(self, expires_at: datetime) -> bool:
        """用于兼容SQLite返回的naive时间并判断过期。"""
        expiry = expires_at
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return expiry <= datetime.now(timezone.utc)

    def _can_change_password(self, user: User | None, current_password: str) -> bool:
        """用于校验账号状态和旧密码。"""
        if user is None or not user.is_active or not user.hashed_password:
            return False
        return verify_password(current_password, user.hashed_password)
