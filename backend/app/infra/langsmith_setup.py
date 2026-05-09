"""
LangSmith initialization helpers.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from app.infra.config import settings

logger = logging.getLogger(__name__)

_langsmith_client: Any | None = None


def configure_langsmith() -> bool:
    global _langsmith_client
    if _langsmith_client is not None:
        return True

    if (
        not settings.LANGSMITH_TRACING
        or not settings.LANGSMITH_API_KEY.strip()
    ):
        logger.info("LangSmith disabled: tracing or API key is not configured")
        return False

    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGSMITH_API_KEY"] = settings.LANGSMITH_API_KEY
    os.environ["LANGCHAIN_API_KEY"] = settings.LANGSMITH_API_KEY
    os.environ["LANGSMITH_ENDPOINT"] = settings.LANGSMITH_ENDPOINT
    os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGSMITH_ENDPOINT
    os.environ["LANGSMITH_PROJECT"] = settings.LANGSMITH_PROJECT
    os.environ["LANGCHAIN_PROJECT"] = settings.LANGSMITH_PROJECT
    if settings.LANGSMITH_WORKSPACE_ID.strip():
        os.environ["LANGSMITH_WORKSPACE_ID"] = settings.LANGSMITH_WORKSPACE_ID

    try:
        from langsmith import Client

        _langsmith_client = Client(
            api_url=settings.LANGSMITH_ENDPOINT,
            api_key=settings.LANGSMITH_API_KEY,
            workspace_id=settings.LANGSMITH_WORKSPACE_ID or None,
        )
        logger.info(
            "LangSmith enabled project=%s endpoint=%s environment=%s",
            settings.LANGSMITH_PROJECT,
            settings.LANGSMITH_ENDPOINT,
            settings.APP_ENV,
        )
        return True
    except Exception as exc:
        logger.exception("LangSmith initialization failed: %s", exc)
        _langsmith_client = None
        return False


def get_langsmith_client() -> Any | None:
    return _langsmith_client


def shutdown_langsmith() -> None:
    global _langsmith_client
    client = _langsmith_client
    if client is None:
        return
    try:
        client.flush()
    except Exception as exc:
        logger.warning("LangSmith flush failed: %s", exc)
    finally:
        _langsmith_client = None
