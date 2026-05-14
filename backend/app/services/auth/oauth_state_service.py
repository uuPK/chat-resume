"""用于提供oauth state service模块能力。"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

from app.infra.security import hash_session_token


@dataclass(frozen=True)
class OAuthStateIssue:
    """用于把原始 state 交给授权地址，同时暴露过期时间给调用方。"""

    value: str
    expires_at: datetime


@dataclass
class _StoredOAuthState:
    expires_at: datetime
    consumed_at: datetime | None = None


class OAuthStateError(ValueError):
    """表示 OAuth state 无法通过回调校验。"""

    error_code = "invalid_state"

    def __init__(self) -> None:
        """用于初始化当前对象。"""
        super().__init__(self.error_code)


class OAuthStateService:
    """用于签发和一次性消费 Google OAuth state。"""

    def __init__(
        self,
        *,
        expires_in: timedelta = timedelta(minutes=10),
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """用于初始化当前对象。"""
        self._expires_in = expires_in
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._states: dict[str, _StoredOAuthState] = {}

    def issue_state(self) -> OAuthStateIssue:
        """生成高熵 state，并只在服务端保存其哈希。"""
        raw_state = secrets.token_urlsafe(48)
        expires_at = self._now() + self._expires_in
        self._states[hash_session_token(raw_state)] = _StoredOAuthState(
            expires_at=expires_at
        )
        return OAuthStateIssue(value=raw_state, expires_at=expires_at)

    def consume_state(self, raw_state: str | None) -> None:
        """校验 state 存在、未过期且未被消费，然后标记为已消费。"""
        if not raw_state:
            raise OAuthStateError()

        stored = self._states.get(hash_session_token(raw_state))
        if stored is None:
            raise OAuthStateError()
        if stored.consumed_at is not None:
            raise OAuthStateError()
        if stored.expires_at < self._now():
            raise OAuthStateError()

        stored.consumed_at = self._now()

    def _now(self) -> datetime:
        """用于处理当前时间。"""
        now = self._clock()
        if now.tzinfo is None:
            return now.replace(tzinfo=timezone.utc)
        return now
