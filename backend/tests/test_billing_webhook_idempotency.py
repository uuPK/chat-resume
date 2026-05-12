from typing import cast

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.services.billing_webhook_service import PayPalWebhookService


class _MissingEventQuery:
    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return None


class _RacingWebhookSession:
    rolled_back = False

    def query(self, *args, **kwargs):
        return _MissingEventQuery()

    def add(self, instance):
        self.instance = instance

    def flush(self):
        raise IntegrityError("insert", {}, Exception("duplicate webhook event"))

    def rollback(self):
        self.rolled_back = True


def test_record_paypal_webhook_event_treats_unique_violation_as_duplicate():
    db = _RacingWebhookSession()

    should_process = PayPalWebhookService(cast(Session, db)).record_event(
        {"id": "WH-RACE", "event_type": "BILLING.SUBSCRIPTION.ACTIVATED"},
        "BILLING.SUBSCRIPTION.ACTIVATED",
    )

    assert should_process is False
    assert db.rolled_back is True
