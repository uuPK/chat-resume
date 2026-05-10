"""
账单与订阅相关数据库模型。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.infra.database import Base


class BillingSubscription(Base):
    """用于保存第三方支付订阅与本地用户的关联。"""

    __tablename__ = "billing_subscriptions"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_subscription_id",
            name="uq_billing_subscriptions_provider_subscription",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String, nullable=False, index=True)
    provider_subscription_id: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    last_provider_event_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )


class BillingWebhookEvent(Base):
    """用于记录已处理的第三方支付 webhook 事件。"""

    __tablename__ = "billing_webhook_events"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "event_id",
            name="uq_billing_webhook_events_provider_event",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    provider: Mapped[str] = mapped_column(String, nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String, nullable=False)
    event_type: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
