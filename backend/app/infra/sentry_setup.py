"""
Sentry initialization helpers.
"""

from __future__ import annotations

import logging

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.types import Event, Hint

from app.infra.config import settings
from app.infra.request_context import get_log_context

logger = logging.getLogger(__name__)


def _before_send(event: Event, hint: Hint) -> Event | None:
    """用于在发送 Sentry 事件前补充当前请求上下文标签。"""
    del hint
    context = get_log_context()
    tags = event.setdefault("tags", {})
    extra = event.setdefault("extra", {})
    for key, value in context.items():
        if value:
            tags[key] = value
            extra[key] = value
    return event


def configure_sentry() -> bool:
    if not settings.SENTRY_DSN.strip():
        logger.info("Sentry disabled: SENTRY_DSN is not configured")
        return False

    sentry_logging = LoggingIntegration(
        level=logging.INFO,
        event_level=logging.ERROR,
    )
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.SENTRY_ENVIRONMENT,
        release=settings.SENTRY_RELEASE or None,
        send_default_pii=settings.SENTRY_SEND_DEFAULT_PII,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
            sentry_logging,
        ],
        before_send=_before_send,
    )
    logger.info(
        "Sentry enabled environment=%s release=%s",
        settings.SENTRY_ENVIRONMENT,
        settings.SENTRY_RELEASE or "-",
    )
    return True
