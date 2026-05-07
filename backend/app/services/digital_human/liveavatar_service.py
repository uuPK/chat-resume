"""HeyGen LiveAvatar 会话服务。

负责创建 LiveAvatar session token，让前端 SDK 可启动实时数字人会话。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from app.infra.config import settings


class LiveAvatarConfigurationError(RuntimeError):
    """用于提示 LiveAvatar 必要环境变量尚未配置。"""


class LiveAvatarService:
    """用于创建 HeyGen LiveAvatar Full mode 会话 token。"""

    def __init__(self) -> None:
        self.api_base = settings.LIVEAVATAR_API_BASE.rstrip("/")
        self.api_key = settings.LIVEAVATAR_API_KEY
        self.avatar_id = settings.LIVEAVATAR_AVATAR_ID
        self.voice_id = settings.LIVEAVATAR_VOICE_ID
        self.context_id = settings.LIVEAVATAR_CONTEXT_ID
        self.llm_configuration_id = settings.LIVEAVATAR_LLM_CONFIGURATION_ID

    def is_configured(self) -> bool:
        """用于判断当前环境是否具备创建 LiveAvatar token 的最小配置。"""
        return bool(
            self.api_key and self.avatar_id and self.voice_id and self.context_id
        )

    async def create_session(
        self,
        *,
        language: str,
        dynamic_variables: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """用于调用 LiveAvatar 创建 Full mode session token。"""
        self._ensure_configured()
        payload: Dict[str, Any] = {
            "avatar_id": self.avatar_id,
            "avatar_persona": {
                "voice_id": self.voice_id,
                "context_id": self.context_id,
                "language": self._normalize_language(language),
            },
            "mode": "FULL",
            "is_sandbox": settings.LIVEAVATAR_SANDBOX,
            "video_settings": {
                "quality": "high",
                "encoding": "H264",
            },
            "max_session_duration": settings.LIVEAVATAR_MAX_SESSION_DURATION,
            "interactivity_type": "CONVERSATIONAL",
            "dynamic_variables": dynamic_variables or {},
        }
        if self.llm_configuration_id:
            payload["llm_configuration_id"] = self.llm_configuration_id

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.api_base}/sessions/token",
                headers={
                    "Content-Type": "application/json",
                    "X-API-KEY": self.api_key,
                },
                json=payload,
            )
            response.raise_for_status()
            result = response.json()

        data = result.get("data", {})
        return {
            "provider": "liveavatar",
            "session_id": data.get("session_id", ""),
            "session_token": data.get("session_token", ""),
            "status": result.get("message", "ready"),
        }

    def _ensure_configured(self) -> None:
        """用于在缺少 LiveAvatar 配置时给出清晰错误。"""
        if not self.is_configured():
            raise LiveAvatarConfigurationError(
                "LiveAvatar is not configured. Set LIVEAVATAR_API_KEY, "
                "LIVEAVATAR_AVATAR_ID, LIVEAVATAR_VOICE_ID, and "
                "LIVEAVATAR_CONTEXT_ID."
            )

    @staticmethod
    def _normalize_language(language: str) -> str:
        """用于把应用内语言码转换为 LiveAvatar 支持的短语言码。"""
        normalized = language.strip().lower()
        if normalized.startswith("zh") or "chinese" in normalized or "中文" in language:
            return "zh"
        return normalized.split("-")[0] or "en"
