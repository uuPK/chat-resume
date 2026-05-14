"""用于初始化和关闭 Langfuse 客户端。"""

from __future__ import annotations

import logging
from typing import Any

from app.infra.config import settings

logger = logging.getLogger(__name__)

_langfuse_client: Any | None = None


def configure_langfuse() -> bool:
    """用于配置Langfuse。"""
    global _langfuse_client
    if _langfuse_client is not None:
        return True

    if (
        not settings.LANGFUSE_PUBLIC_KEY.strip()
        or not settings.LANGFUSE_SECRET_KEY.strip()
    ):
        logger.debug("Langfuse disabled: credentials are not configured")
        return False

    try:
        from langfuse import Langfuse

        _langfuse_client = Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_HOST,
            environment=settings.APP_ENV,
            release=settings.SENTRY_RELEASE or None,
            sample_rate=settings.LANGFUSE_SAMPLE_RATE,
            debug=settings.LANGFUSE_DEBUG,
            tracing_enabled=True,
        )
        logger.info(
            "Langfuse enabled host=%s environment=%s sample_rate=%s",
            settings.LANGFUSE_HOST,
            settings.APP_ENV,
            settings.LANGFUSE_SAMPLE_RATE,
        )
        return True
    except Exception as exc:
        logger.exception("Langfuse initialization failed: %s", exc)
        _langfuse_client = None
        return False


def get_langfuse_client() -> Any | None:
    """用于获取Langfuse客户端。"""
    return _langfuse_client


def shutdown_langfuse() -> None:
    """用于关闭Langfuse。"""
    global _langfuse_client
    client = _langfuse_client
    if client is None:
        return
    try:
        client.flush()
        client.shutdown()
    except Exception as exc:
        logger.warning("Langfuse shutdown failed: %s", exc)
    finally:
        _langfuse_client = None
