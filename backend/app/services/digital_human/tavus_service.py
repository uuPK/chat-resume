"""Tavus 数字人会话服务。

把 Tavus API 调用集中在服务层，避免前端接触供应商密钥。
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from app.infra.config import settings


class TavusConfigurationError(RuntimeError):
    """用于提示 Tavus 必要环境变量尚未配置。"""


class TavusService:
    """用于创建和结束 Tavus 实时数字人会话。"""

    def __init__(self) -> None:
        self.api_base = settings.TAVUS_API_BASE.rstrip("/")
        self.api_key = settings.TAVUS_API_KEY
        self.replica_id = settings.TAVUS_REPLICA_ID
        self.persona_id = settings.TAVUS_PERSONA_ID

    def is_configured(self) -> bool:
        """用于判断当前环境是否具备创建 Tavus 会话的最小配置。"""
        return bool(self.api_key and self.replica_id and self.persona_id)

    async def create_conversation(
        self,
        *,
        conversation_name: str,
        conversational_context: str,
        custom_greeting: Optional[str] = None,
    ) -> Dict[str, Any]:
        """用于调用 Tavus 创建一场实时数字人 conversation。"""
        self._ensure_configured()
        payload: Dict[str, Any] = {
            "replica_id": self.replica_id,
            "persona_id": self.persona_id,
            "conversation_name": conversation_name,
            "conversational_context": conversational_context,
            "require_auth": settings.TAVUS_REQUIRE_AUTH,
            "test_mode": settings.TAVUS_TEST_MODE,
            "max_participants": 2,
        }
        if custom_greeting:
            payload["custom_greeting"] = custom_greeting

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.api_base}/conversations",
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": self.api_key,
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        join_url = self._build_join_url(
            data.get("conversation_url", ""), data.get("meeting_token")
        )
        return {
            "provider": "tavus",
            "conversation_id": data.get("conversation_id", ""),
            "conversation_url": data.get("conversation_url", ""),
            "join_url": join_url,
            "status": data.get("status", ""),
            "meeting_token": data.get("meeting_token"),
        }

    async def end_conversation(self, conversation_id: str) -> None:
        """用于释放 Tavus conversation，避免持续占用并发和分钟数。"""
        self._ensure_configured()
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"{self.api_base}/conversations/{conversation_id}/end",
                headers={"x-api-key": self.api_key},
            )
            response.raise_for_status()

    def _ensure_configured(self) -> None:
        """用于在缺少 Tavus 配置时给出清晰错误。"""
        if not self.is_configured():
            raise TavusConfigurationError(
                "Tavus is not configured. Set TAVUS_API_KEY, "
                "TAVUS_REPLICA_ID, and TAVUS_PERSONA_ID."
            )

    @staticmethod
    def _build_join_url(conversation_url: str, meeting_token: Optional[str]) -> str:
        """用于把私有房间 token 安全追加到 Tavus/Daily URL。"""
        if not conversation_url or not meeting_token:
            return conversation_url
        parts = urlsplit(conversation_url)
        query = dict(parse_qsl(parts.query))
        query["t"] = meeting_token
        return urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
        )
