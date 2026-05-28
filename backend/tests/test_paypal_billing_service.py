"""用于覆盖 test_paypal_billing_service.py 对应的回归测试。"""

import json
from urllib.parse import parse_qs

import httpx
import pytest

from app.services.paypal_billing_service import (
    PayPalBillingConfig,
    PayPalBillingService,
)


@pytest.mark.asyncio
async def test_paypal_billing_service_creates_subscription_with_approval_url():
    """用于验证PayPal计费servicecreates订阅withapprovalurl。"""
    seen_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        """用于处理handler。"""
        seen_requests.append(request)
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(
                200,
                json={"access_token": "paypal-access-token", "token_type": "Bearer"},
            )
        if request.url.path == "/v1/billing/subscriptions":
            return httpx.Response(
                201,
                json={
                    "id": "I-TESTSUB123",
                    "status": "APPROVAL_PENDING",
                    "links": [
                        {
                            "href": "https://www.paypal.com/checkoutnow?token=I-TESTSUB123",
                            "rel": "approve",
                            "method": "GET",
                        }
                    ],
                },
            )
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        service = PayPalBillingService(
            PayPalBillingConfig(
                client_id="paypal-client-id",
                client_secret="paypal-client-secret",
                plan_id="P-TESTPLAN",
                api_base="https://api-m.sandbox.paypal.com",
                return_url="http://localhost:3000/settings?billing=success",
                cancel_url="http://localhost:3000/settings?billing=cancelled",
            ),
            http_client=http_client,
        )

        result = await service.create_subscription(user_id=42)

    assert result == {
        "provider": "paypal",
        "subscription_id": "I-TESTSUB123",
        "status": "APPROVAL_PENDING",
        "approval_url": "https://www.paypal.com/checkoutnow?token=I-TESTSUB123",
    }
    assert len(seen_requests) == 2
    token_request = seen_requests[0]
    assert token_request.method == "POST"
    assert str(token_request.url) == "https://api-m.sandbox.paypal.com/v1/oauth2/token"
    assert parse_qs(token_request.content.decode())["grant_type"] == [
        "client_credentials"
    ]
    assert token_request.headers["Authorization"].startswith("Basic ")

    subscription_request = seen_requests[1]
    assert subscription_request.method == "POST"
    assert str(subscription_request.url) == (
        "https://api-m.sandbox.paypal.com/v1/billing/subscriptions"
    )
    assert subscription_request.headers["Authorization"] == "Bearer paypal-access-token"
    assert (
        subscription_request.headers["PayPal-Request-Id"] == "user-42-plan-P-TESTPLAN"
    )
    assert subscription_request.headers["Content-Type"] == "application/json"
    payload = json.loads(subscription_request.content)
    assert payload["plan_id"] == "P-TESTPLAN"
    assert payload["application_context"]["return_url"] == (
        "http://localhost:3000/settings?billing=success"
    )


@pytest.mark.asyncio
async def test_paypal_billing_service_reads_current_plan_price_from_paypal():
    """用于验证PayPal计费servicereadscurrentplanpricefromPayPal。"""
    seen_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        """用于处理handler。"""
        seen_requests.append(request)
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(
                200,
                json={"access_token": "paypal-access-token", "token_type": "Bearer"},
            )
        if request.url.path == "/v1/billing/plans/P-TESTPLAN":
            return httpx.Response(
                200,
                json={
                    "id": "P-TESTPLAN",
                    "name": "OfferMaster Plus",
                    "billing_cycles": [
                        {
                            "tenure_type": "REGULAR",
                            "pricing_scheme": {
                                "fixed_price": {
                                    "value": "10.00",
                                    "currency_code": "USD",
                                }
                            },
                        }
                    ],
                },
            )
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        service = PayPalBillingService(
            PayPalBillingConfig(
                client_id="paypal-client-id",
                client_secret="paypal-client-secret",
                plan_id="P-TESTPLAN",
                api_base="https://api-m.sandbox.paypal.com",
                return_url="http://localhost:3000/settings?billing=success",
                cancel_url="http://localhost:3000/settings?billing=cancelled",
            ),
            http_client=http_client,
        )

        plan = await service.get_plan()

    assert plan == {
        "id": "P-TESTPLAN",
        "name": "OfferMaster Plus",
        "price": "10.00",
        "currency_code": "USD",
    }
    assert [request.url.path for request in seen_requests] == [
        "/v1/oauth2/token",
        "/v1/billing/plans/P-TESTPLAN",
    ]


@pytest.mark.asyncio
async def test_paypal_billing_service_reads_subscription_status_from_paypal():
    """用于验证PayPal计费servicereads订阅状态fromPayPal。"""
    seen_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        """用于处理handler。"""
        seen_requests.append(request)
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(
                200,
                json={"access_token": "paypal-access-token", "token_type": "Bearer"},
            )
        if request.url.path == "/v1/billing/subscriptions/I-SYNC123":
            return httpx.Response(
                200,
                json={
                    "id": "I-SYNC123",
                    "status": "ACTIVE",
                    "plan_id": "P-TESTPLAN",
                },
            )
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        service = PayPalBillingService(
            PayPalBillingConfig(
                client_id="paypal-client-id",
                client_secret="paypal-client-secret",
                plan_id="P-TESTPLAN",
                api_base="https://api-m.sandbox.paypal.com",
                return_url="http://localhost:3000/settings?billing=success",
                cancel_url="http://localhost:3000/settings?billing=cancelled",
            ),
            http_client=http_client,
        )

        subscription = await service.get_subscription(subscription_id="I-SYNC123")

    assert subscription == {
        "provider": "paypal",
        "subscription_id": "I-SYNC123",
        "status": "ACTIVE",
        "raw_payload": {
            "id": "I-SYNC123",
            "status": "ACTIVE",
            "plan_id": "P-TESTPLAN",
        },
    }
    assert [request.url.path for request in seen_requests] == [
        "/v1/oauth2/token",
        "/v1/billing/subscriptions/I-SYNC123",
    ]


@pytest.mark.asyncio
async def test_paypal_billing_service_cancels_subscription():
    """用于验证PayPal计费servicecancels订阅。"""
    seen_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        """用于处理handler。"""
        seen_requests.append(request)
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(
                200,
                json={"access_token": "paypal-access-token", "token_type": "Bearer"},
            )
        if request.url.path == "/v1/billing/subscriptions/I-CANCEL123/cancel":
            return httpx.Response(204)
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        service = PayPalBillingService(
            PayPalBillingConfig(
                client_id="paypal-client-id",
                client_secret="paypal-client-secret",
                plan_id="P-TESTPLAN",
                api_base="https://api-m.sandbox.paypal.com",
                return_url="http://localhost:3000/settings?billing=success",
                cancel_url="http://localhost:3000/settings?billing=cancelled",
            ),
            http_client=http_client,
        )

        await service.cancel_subscription(subscription_id="I-CANCEL123")

    assert [request.url.path for request in seen_requests] == [
        "/v1/oauth2/token",
        "/v1/billing/subscriptions/I-CANCEL123/cancel",
    ]
    cancel_request = seen_requests[1]
    assert cancel_request.method == "POST"
    assert cancel_request.headers["Authorization"] == "Bearer paypal-access-token"
    assert json.loads(cancel_request.content) == {
        "reason": "User requested cancellation"
    }


@pytest.mark.asyncio
async def test_paypal_billing_service_verifies_webhook_signature():
    """用于验证PayPal计费serviceverifieswebhooksignature。"""
    seen_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        """用于处理handler。"""
        seen_requests.append(request)
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(
                200,
                json={"access_token": "paypal-access-token", "token_type": "Bearer"},
            )
        if request.url.path == "/v1/notifications/verify-webhook-signature":
            return httpx.Response(200, json={"verification_status": "SUCCESS"})
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        service = PayPalBillingService(
            PayPalBillingConfig(
                client_id="paypal-client-id",
                client_secret="paypal-client-secret",
                plan_id="P-TESTPLAN",
                api_base="https://api-m.sandbox.paypal.com",
                return_url="http://localhost:3000/settings?billing=success",
                cancel_url="http://localhost:3000/settings?billing=cancelled",
                webhook_id="WH-TEST",
            ),
            http_client=http_client,
        )

        await service.verify_webhook(
            headers={
                "paypal-auth-algo": "SHA256withRSA",
                "paypal-cert-url": "https://api-m.sandbox.paypal.com/certs/test",
                "paypal-transmission-id": "transmission-id",
                "paypal-transmission-sig": "signature",
                "paypal-transmission-time": "2026-05-10T14:00:00Z",
            },
            event={
                "id": "WH-EVENT",
                "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
                "resource": {"id": "I-TESTSUB123", "status": "ACTIVE"},
            },
        )

    assert len(seen_requests) == 2
    verify_request = seen_requests[1]
    assert verify_request.method == "POST"
    assert str(verify_request.url) == (
        "https://api-m.sandbox.paypal.com/v1/notifications/verify-webhook-signature"
    )
    assert verify_request.headers["Authorization"] == "Bearer paypal-access-token"
    payload = json.loads(verify_request.content)
    assert payload["webhook_id"] == "WH-TEST"
    assert payload["transmission_id"] == "transmission-id"
    assert payload["transmission_sig"] == "signature"
    assert payload["webhook_event"]["resource"]["id"] == "I-TESTSUB123"
