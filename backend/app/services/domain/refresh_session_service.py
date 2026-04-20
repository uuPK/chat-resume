"""
刷新会话服务模块

用于集中处理刷新会话的签发、轮换、吊销和有效性校验。
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.infra.config import settings
from app.infra.security import generate_session_token, hash_session_token
from app.models.refresh_session import RefreshSession


def _coerce_database_datetime(value: datetime) -> datetime:
    """用于兼容 SQLite 把时区时间读成 naive datetime 的情况。"""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


class RefreshSessionService:
    """用于管理刷新令牌对应的服务端会话生命周期。"""

    def __init__(self, db: Session):
        """用于保存当前请求复用的数据库会话。"""
        self.db = db

    def create_session(self, user_id: int) -> tuple[RefreshSession, str]:
        """用于给用户签发一条新的刷新会话记录。"""
        raw_token = generate_session_token()
        session = RefreshSession(
            user_id=user_id,
            token_hash=hash_session_token(raw_token),
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.REFRESH_SESSION_EXPIRE_DAYS),
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session, raw_token

    def get_session_by_token(self, raw_token: str) -> RefreshSession | None:
        """用于通过原始刷新令牌查找服务端会话记录。"""
        return (
            self.db.query(RefreshSession)
            .filter(RefreshSession.token_hash == hash_session_token(raw_token))
            .first()
        )

    def is_session_active(self, session: RefreshSession | None) -> bool:
        """用于判断刷新会话当前是否仍然允许继续使用。"""
        if session is None:
            return False
        if session.revoked_at is not None:
            return False
        return _coerce_database_datetime(session.expires_at) >= datetime.now(
            timezone.utc
        )

    def touch_session(self, session: RefreshSession) -> RefreshSession:
        """用于记录一次成功刷新，便于后续排查和审计。"""
        session.last_used_at = datetime.now(timezone.utc)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def revoke_session(
        self,
        session: RefreshSession,
        *,
        replaced_by_session_id: int | None = None,
    ) -> RefreshSession:
        """用于把指定刷新会话标记为已失效。"""
        session.revoked_at = datetime.now(timezone.utc)
        session.replaced_by_session_id = replaced_by_session_id
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session
