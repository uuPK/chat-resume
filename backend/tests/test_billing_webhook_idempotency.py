"""用于覆盖 test_billing_webhook_idempotency.py 对应的回归测试。"""

from typing import cast

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.services.billing_webhook_service import PayPalWebhookService


class _MissingEventQuery:
    def filter(self, *args, **kwargs):
        """用于处理filter。"""
        return self

    def first(self):
        """用于处理first。"""
        return None


class _RacingWebhookSession:
    rolled_back = False

    def query(self, *args, **kwargs):
        """用于处理query。"""
        return _MissingEventQuery()

    def add(self, instance):
        """用于处理add。"""
        self.instance = instance

    def flush(self):
        """用于处理flush。"""
        raise IntegrityError("insert", {}, Exception("duplicate webhook event"))

    def rollback(self):
        """用于处理rollback。"""
        self.rolled_back = True


def test_record_paypal_webhook_event_treats_unique_violation_as_duplicate():
    """用于验证recordPayPalwebhook事件treatsuniqueviolationasduplicate。"""
    db = _RacingWebhookSession()

    should_process = PayPalWebhookService(cast(Session, db)).record_event(
        {"id": "WH-RACE", "event_type": "BILLING.SUBSCRIPTION.ACTIVATED"},
        "BILLING.SUBSCRIPTION.ACTIVATED",
    )

    assert should_process is False
    assert db.rolled_back is True
