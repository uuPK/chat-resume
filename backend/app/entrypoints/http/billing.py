"""
账单与支付相关 API 端点。
"""

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.entrypoints.http.deps import get_current_user
from app.infra.config import settings
from app.infra.database import get_db
from app.models.billing import BillingSubscription, BillingWebhookEvent
from app.services.paypal_billing_service import (
    PayPalBillingConfigurationError,
    PayPalBillingError,
    PayPalBillingService,
)

router = APIRouter()
logger = logging.getLogger(__name__)
_PAYPAL_SUBSCRIPTION_STATUS_EVENTS = {
    "BILLING.SUBSCRIPTION.ACTIVATED",
    "BILLING.SUBSCRIPTION.CANCELLED",
    "BILLING.SUBSCRIPTION.EXPIRED",
    "BILLING.SUBSCRIPTION.SUSPENDED",
}
_OPEN_PAYPAL_SUBSCRIPTION_STATUSES = {"APPROVAL_PENDING", "ACTIVE"}


def _is_subscription_active(status_value: str | None) -> bool:
    return str(status_value or "").upper() == "ACTIVE"


def _subscription_status_payload(
    subscription: BillingSubscription | None,
) -> dict[str, Any]:
    if subscription is None:
        return {
            "provider": None,
            "subscription_id": None,
            "status": "FREE",
            "is_active": False,
        }
    return {
        "provider": subscription.provider,
        "subscription_id": subscription.provider_subscription_id,
        "status": subscription.status,
        "is_active": _is_subscription_active(subscription.status),
    }


def _paypal_checkout_payload(
    subscription: BillingSubscription,
) -> dict[str, str] | None:
    payload = subscription.raw_payload
    if not isinstance(payload, dict):
        return None
    approval_url = payload.get("approval_url")
    if not isinstance(approval_url, str) or not approval_url.strip():
        return None
    return {
        "provider": subscription.provider,
        "subscription_id": subscription.provider_subscription_id,
        "status": subscription.status,
        "approval_url": approval_url,
    }


def _open_paypal_subscription(
    db: Session,
    user_id: int,
) -> BillingSubscription | None:
    return (
        db.query(BillingSubscription)
        .filter(
            BillingSubscription.user_id == user_id,
            BillingSubscription.provider == "paypal",
            BillingSubscription.status.in_(_OPEN_PAYPAL_SUBSCRIPTION_STATUSES),
        )
        .order_by(BillingSubscription.id.desc())
        .first()
    )


def _paypal_subscription_by_provider_id(
    db: Session,
    subscription_id: str,
) -> BillingSubscription | None:
    return (
        db.query(BillingSubscription)
        .filter(
            BillingSubscription.provider == "paypal",
            BillingSubscription.provider_subscription_id == subscription_id,
        )
        .first()
    )


def _current_subscription_for_user(
    db: Session,
    user_id: int,
) -> BillingSubscription | None:
    active_subscription = (
        db.query(BillingSubscription)
        .filter(
            BillingSubscription.user_id == user_id,
            BillingSubscription.status == "ACTIVE",
        )
        .order_by(BillingSubscription.id.desc())
        .first()
    )
    if active_subscription is not None:
        return active_subscription

    pending_subscription = (
        db.query(BillingSubscription)
        .filter(
            BillingSubscription.user_id == user_id,
            BillingSubscription.status == "APPROVAL_PENDING",
        )
        .order_by(BillingSubscription.id.desc())
        .first()
    )
    if pending_subscription is not None:
        return pending_subscription

    return (
        db.query(BillingSubscription)
        .filter(BillingSubscription.user_id == user_id)
        .order_by(BillingSubscription.id.desc())
        .first()
    )


def _subscription_resource_from_event(event: dict[str, Any]) -> tuple[str, str] | None:
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


def _paypal_event_id(event: dict[str, Any]) -> str | None:
    event_id = event.get("id")
    if not isinstance(event_id, str) or not event_id.strip():
        return None
    return event_id


def _record_paypal_webhook_event(
    db: Session,
    event: dict[str, Any],
    event_type: object,
) -> bool:
    event_id = _paypal_event_id(event)
    if event_id is None:
        return True

    existing_event = (
        db.query(BillingWebhookEvent.id)
        .filter(
            BillingWebhookEvent.provider == "paypal",
            BillingWebhookEvent.event_id == event_id,
        )
        .first()
    )
    if existing_event is not None:
        logger.info(
            "billing.paypal.duplicate_webhook_ignored",
            extra={"paypal_event_id": event_id, "paypal_event_type": event_type},
        )
        return False

    try:
        db.add(
            BillingWebhookEvent(
                provider="paypal",
                event_id=event_id,
                event_type=event_type if isinstance(event_type, str) else None,
                raw_payload=event,
            )
        )
        db.flush()
    except IntegrityError:
        db.rollback()
        logger.info(
            "billing.paypal.duplicate_webhook_ignored",
            extra={"paypal_event_id": event_id, "paypal_event_type": event_type},
        )
        return False
    return True


def _parse_paypal_event_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _stored_paypal_event_time(subscription: BillingSubscription) -> datetime | None:
    stored_event_time = subscription.last_provider_event_time
    if stored_event_time is not None:
        if stored_event_time.tzinfo is None:
            stored_event_time = stored_event_time.replace(tzinfo=timezone.utc)
        return stored_event_time.astimezone(timezone.utc)

    payload = subscription.raw_payload
    if not isinstance(payload, dict):
        return None
    return _parse_paypal_event_time(payload.get("create_time"))


def _is_stale_paypal_event(
    subscription: BillingSubscription,
    event: dict[str, Any],
) -> bool:
    stored_time = _stored_paypal_event_time(subscription)
    if stored_time is None:
        return False
    incoming_time = _parse_paypal_event_time(event.get("create_time"))
    if incoming_time is None:
        return True
    return incoming_time <= stored_time


def _paypal_subscription_plan_matches(raw_payload: object) -> bool:
    if not isinstance(raw_payload, dict):
        return False
    plan_id = raw_payload.get("plan_id")
    expected_plan_id = settings.PAYPAL_PLAN_ID.strip()
    return isinstance(plan_id, str) and plan_id.strip() == expected_plan_id


def _paypal_event_plan_matches(event: dict[str, Any]) -> bool:
    resource = event.get("resource")
    return _paypal_subscription_plan_matches(resource)


@router.post("/paypal/subscriptions")
async def create_paypal_subscription(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """为当前登录用户创建 PayPal 订阅并返回 PayPal 审批链接。"""
    existing_subscription = _open_paypal_subscription(db, current_user["id"])
    if existing_subscription is not None:
        existing_checkout = _paypal_checkout_payload(existing_subscription)
        if existing_checkout is not None:
            return existing_checkout
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="paypal_subscription_already_active",
        )

    try:
        result = await PayPalBillingService().create_subscription(
            user_id=current_user["id"]
        )
    except PayPalBillingConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except PayPalBillingError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    subscription = BillingSubscription(
        user_id=current_user["id"],
        provider=result["provider"],
        provider_subscription_id=result["subscription_id"],
        status=result["status"],
        raw_payload=result,
    )
    db.add(subscription)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing_subscription = _paypal_subscription_by_provider_id(
            db, result["subscription_id"]
        )
        if (
            existing_subscription is not None
            and existing_subscription.user_id == current_user["id"]
        ):
            existing_checkout = _paypal_checkout_payload(existing_subscription)
            if existing_checkout is not None:
                return existing_checkout
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="paypal_subscription_already_exists",
        ) from exc
    logger.info(
        "billing.paypal.subscription_created",
        extra={
            "user_id": current_user["id"],
            "provider_subscription_id": result["subscription_id"],
            "paypal_status": result["status"],
        },
    )
    return result


@router.get("/status")
async def get_billing_status(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """返回当前用户的本地订阅状态。"""
    subscription = _current_subscription_for_user(db, current_user["id"])
    return _subscription_status_payload(subscription)


@router.get("/paypal/plan")
async def get_paypal_plan(current_user: dict = Depends(get_current_user)):
    """返回当前 PayPal 计划的真实价格信息。"""
    try:
        return await PayPalBillingService().get_plan()
    except PayPalBillingConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except PayPalBillingError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.get("/paypal/subscriptions/{subscription_id}/sync")
async def sync_paypal_subscription(
    subscription_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """从 PayPal 主动同步当前用户的一条订阅状态。"""
    subscription = (
        db.query(BillingSubscription)
        .filter(
            BillingSubscription.user_id == current_user["id"],
            BillingSubscription.provider == "paypal",
            BillingSubscription.provider_subscription_id == subscription_id,
        )
        .first()
    )
    if subscription is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="paypal_subscription_not_found",
        )

    try:
        result = await PayPalBillingService().get_subscription(
            subscription_id=subscription_id
        )
    except PayPalBillingConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except PayPalBillingError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    raw_payload = result.get("raw_payload")
    if not _paypal_subscription_plan_matches(raw_payload):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="paypal_subscription_plan_mismatch",
        )

    subscription.status = str(result["status"])
    subscription.raw_payload = raw_payload if isinstance(raw_payload, dict) else result
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return _subscription_status_payload(subscription)


@router.post("/paypal/subscriptions/{subscription_id}/cancel")
async def cancel_paypal_subscription(
    subscription_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """取消当前用户的一条 PayPal 订阅。"""
    subscription = (
        db.query(BillingSubscription)
        .filter(
            BillingSubscription.user_id == current_user["id"],
            BillingSubscription.provider == "paypal",
            BillingSubscription.provider_subscription_id == subscription_id,
        )
        .first()
    )
    if subscription is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="paypal_subscription_not_found",
        )

    try:
        await PayPalBillingService().cancel_subscription(
            subscription_id=subscription_id
        )
    except PayPalBillingConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except PayPalBillingError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    subscription.status = "CANCELLED"
    payload = (
        subscription.raw_payload if isinstance(subscription.raw_payload, dict) else {}
    )
    subscription.raw_payload = {**payload, "status": "CANCELLED"}
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return _subscription_status_payload(subscription)


@router.post("/paypal/webhook")
async def handle_paypal_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """验证并接收 PayPal webhook。"""
    event: dict[str, Any] = await request.json()
    event_type = event.get("event_type")
    logger.info(
        "billing.paypal.webhook_received",
        extra={"paypal_event_type": event_type},
    )
    try:
        await PayPalBillingService().verify_webhook(
            headers=dict(request.headers),
            event=event,
        )
    except PayPalBillingConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except PayPalBillingError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    if not _record_paypal_webhook_event(db, event, event_type):
        return {"received": True}

    if event_type in _PAYPAL_SUBSCRIPTION_STATUS_EVENTS:
        subscription_resource = _subscription_resource_from_event(event)
        if subscription_resource is not None:
            subscription_id, status_value = subscription_resource
            if not _paypal_event_plan_matches(event):
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="paypal_subscription_plan_mismatch",
                )
            subscription = (
                db.query(BillingSubscription)
                .filter(
                    BillingSubscription.provider == "paypal",
                    BillingSubscription.provider_subscription_id == subscription_id,
                )
                .first()
            )
            if subscription is not None:
                if _is_stale_paypal_event(subscription, event):
                    logger.warning(
                        "billing.paypal.stale_webhook_ignored",
                        extra={
                            "provider_subscription_id": subscription_id,
                            "paypal_status": status_value,
                            "user_id": subscription.user_id,
                        },
                    )
                    db.commit()
                    return {"received": True}
                subscription.status = status_value
                incoming_time = _parse_paypal_event_time(event.get("create_time"))
                if incoming_time is not None:
                    subscription.last_provider_event_time = incoming_time
                subscription.raw_payload = event
                db.add(subscription)
                db.commit()
                logger.info(
                    "billing.paypal.subscription_status_updated",
                    extra={
                        "provider_subscription_id": subscription_id,
                        "paypal_status": status_value,
                        "user_id": subscription.user_id,
                    },
                )
            else:
                logger.warning(
                    "billing.paypal.subscription_not_found",
                    extra={
                        "provider_subscription_id": subscription_id,
                        "paypal_status": status_value,
                    },
                )
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="paypal_subscription_not_found",
                )
        else:
            logger.warning(
                "billing.paypal.webhook_resource_missing",
                extra={"paypal_event_type": event_type},
            )

    db.commit()
    return {"received": True}
