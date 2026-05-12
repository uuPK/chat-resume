"""用于处理 PayPal webhook 的幂等记录和本地订阅状态机。"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infra.config import settings
from app.models.billing import BillingSubscription, BillingWebhookEvent

logger = logging.getLogger(__name__)

_PAYPAL_SUBSCRIPTION_STATUS_EVENTS = {
    "BILLING.SUBSCRIPTION.ACTIVATED",
    "BILLING.SUBSCRIPTION.CANCELLED",
    "BILLING.SUBSCRIPTION.EXPIRED",
    "BILLING.SUBSCRIPTION.SUSPENDED",
}


class PayPalWebhookService:
    """用于把 PayPal webhook 事件转换为本地账单状态。"""

    def __init__(self, db: Session):
        """用于初始化 webhook 状态机所需数据库会话。"""
        self.db = db

    def handle_event(
        self,
        event: dict[str, Any],
        event_type: object,
    ) -> dict[str, bool]:
        """用于幂等处理一条已验签的 PayPal webhook 事件。"""
        if not self.record_event(event, event_type):
            return {"received": True}
        if event_type in _PAYPAL_SUBSCRIPTION_STATUS_EVENTS:
            self._handle_subscription_status_event(event, event_type)
        self.db.commit()
        return {"received": True}

    def record_event(self, event: dict[str, Any], event_type: object) -> bool:
        """用于记录 webhook 事件并识别重复事件。"""
        event_id = self._event_id(event)
        if event_id is None:
            return True

        existing_event = (
            self.db.query(BillingWebhookEvent.id)
            .filter(
                BillingWebhookEvent.provider == "paypal",
                BillingWebhookEvent.event_id == event_id,
            )
            .first()
        )
        if existing_event is not None:
            self._log_duplicate_event(event_id, event_type)
            return False

        try:
            self.db.add(
                BillingWebhookEvent(
                    provider="paypal",
                    event_id=event_id,
                    event_type=event_type if isinstance(event_type, str) else None,
                    raw_payload=event,
                )
            )
            self.db.flush()
        except IntegrityError:
            self.db.rollback()
            self._log_duplicate_event(event_id, event_type)
            return False
        return True

    def _handle_subscription_status_event(
        self,
        event: dict[str, Any],
        event_type: object,
    ) -> None:
        """用于处理 PayPal 订阅状态类 webhook。"""
        subscription_resource = self._subscription_resource(event)
        if subscription_resource is None:
            logger.warning(
                "billing.paypal.webhook_resource_missing",
                extra={"paypal_event_type": event_type},
            )
            return

        subscription_id, status_value = subscription_resource
        if not self._event_plan_matches(event):
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="paypal_subscription_plan_mismatch",
            )
        subscription = self._subscription_by_provider_id(subscription_id)
        if subscription is None:
            logger.warning(
                "billing.paypal.subscription_not_found",
                extra={
                    "provider_subscription_id": subscription_id,
                    "paypal_status": status_value,
                },
            )
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="paypal_subscription_not_found",
            )
        if self._is_stale_event(subscription, event):
            logger.warning(
                "billing.paypal.stale_webhook_ignored",
                extra={
                    "provider_subscription_id": subscription_id,
                    "paypal_status": status_value,
                    "user_id": subscription.user_id,
                },
            )
            return

        subscription.status = status_value
        incoming_time = self._parse_event_time(event.get("create_time"))
        if incoming_time is not None:
            subscription.last_provider_event_time = incoming_time
        subscription.raw_payload = event
        self.db.add(subscription)
        logger.info(
            "billing.paypal.subscription_status_updated",
            extra={
                "provider_subscription_id": subscription_id,
                "paypal_status": status_value,
                "user_id": subscription.user_id,
            },
        )

    def _subscription_by_provider_id(
        self,
        subscription_id: str,
    ) -> BillingSubscription | None:
        """用于按 PayPal subscription id 查询本地订阅。"""
        return (
            self.db.query(BillingSubscription)
            .filter(
                BillingSubscription.provider == "paypal",
                BillingSubscription.provider_subscription_id == subscription_id,
            )
            .first()
        )

    @staticmethod
    def _event_id(event: dict[str, Any]) -> str | None:
        """用于读取 PayPal webhook 事件 id。"""
        event_id = event.get("id")
        if not isinstance(event_id, str) or not event_id.strip():
            return None
        return event_id

    @staticmethod
    def _subscription_resource(event: dict[str, Any]) -> tuple[str, str] | None:
        """用于读取 PayPal webhook 中的订阅 id 和状态。"""
        resource = event.get("resource")
        if not isinstance(resource, dict):
            return None
        subscription_id = resource.get("id")
        status_value = resource.get("status")
        if not isinstance(subscription_id, str) or not subscription_id.strip():
            return None
        if not isinstance(status_value, str) or not status_value.strip():
            return None
        return subscription_id, status_value

    @staticmethod
    def _parse_event_time(value: object) -> datetime | None:
        """用于解析 PayPal webhook 事件时间。"""
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _stored_event_time(self, subscription: BillingSubscription) -> datetime | None:
        """用于读取本地订阅已处理过的最新 provider 事件时间。"""
        stored_event_time = subscription.last_provider_event_time
        if stored_event_time is not None:
            if stored_event_time.tzinfo is None:
                stored_event_time = stored_event_time.replace(tzinfo=timezone.utc)
            return stored_event_time.astimezone(timezone.utc)

        payload = subscription.raw_payload
        if not isinstance(payload, dict):
            return None
        return self._parse_event_time(payload.get("create_time"))

    def _is_stale_event(
        self,
        subscription: BillingSubscription,
        event: dict[str, Any],
    ) -> bool:
        """用于判断 PayPal webhook 是否旧于本地已处理事件。"""
        stored_time = self._stored_event_time(subscription)
        if stored_time is None:
            return False
        incoming_time = self._parse_event_time(event.get("create_time"))
        if incoming_time is None:
            return True
        return incoming_time <= stored_time

    @staticmethod
    def _subscription_plan_matches(raw_payload: object) -> bool:
        """用于判断 PayPal 订阅 payload 是否属于当前计划。"""
        if not isinstance(raw_payload, dict):
            return False
        plan_id = raw_payload.get("plan_id")
        expected_plan_id = settings.PAYPAL_PLAN_ID.strip()
        return isinstance(plan_id, str) and plan_id.strip() == expected_plan_id

    def _event_plan_matches(self, event: dict[str, Any]) -> bool:
        """用于判断 PayPal webhook 是否属于当前计划。"""
        return self._subscription_plan_matches(event.get("resource"))

    @staticmethod
    def _log_duplicate_event(event_id: str, event_type: object) -> None:
        """用于记录重复 webhook 被忽略的日志。"""
        logger.info(
            "billing.paypal.duplicate_webhook_ignored",
            extra={"paypal_event_id": event_id, "paypal_event_type": event_type},
        )


__all__ = ["PayPalWebhookService"]
