"""用于封装 PayPal 订阅计费接口。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.infra.config import settings


class PayPalBillingError(Exception):
    """Raised when PayPal returns an unusable response or rejects a request."""


class PayPalBillingConfigurationError(Exception):
    """Raised when required PayPal settings are missing."""

    def __init__(self, missing_names: list[str]):
        """用于初始化当前对象。"""
        self.missing_names = missing_names
        super().__init__(
            "Missing PayPal billing configuration: " + ", ".join(missing_names)
        )


@dataclass(frozen=True)
class PayPalBillingConfig:
    client_id: str
    client_secret: str
    plan_id: str
    api_base: str
    return_url: str
    cancel_url: str
    webhook_id: str = ""

    @classmethod
    def from_settings(cls, settings_obj: object) -> PayPalBillingConfig:
        """用于从应用配置创建服务实例。"""
        required = {
            "PAYPAL_CLIENT_ID": str(
                getattr(settings_obj, "PAYPAL_CLIENT_ID", "")
            ).strip(),
            "PAYPAL_CLIENT_SECRET": str(
                getattr(settings_obj, "PAYPAL_CLIENT_SECRET", "")
            ).strip(),
            "PAYPAL_PLAN_ID": str(getattr(settings_obj, "PAYPAL_PLAN_ID", "")).strip(),
            "PAYPAL_WEBHOOK_ID": str(
                getattr(settings_obj, "PAYPAL_WEBHOOK_ID", "")
            ).strip(),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise PayPalBillingConfigurationError(missing)

        frontend_url = str(getattr(settings_obj, "FRONTEND_URL", "")).rstrip("/")
        return cls(
            client_id=required["PAYPAL_CLIENT_ID"],
            client_secret=required["PAYPAL_CLIENT_SECRET"],
            plan_id=required["PAYPAL_PLAN_ID"],
            api_base=str(
                getattr(
                    settings_obj,
                    "PAYPAL_API_BASE",
                    "https://api-m.sandbox.paypal.com",
                )
            ).rstrip("/"),
            return_url=f"{frontend_url}/settings?billing=success",
            cancel_url=f"{frontend_url}/settings?billing=cancelled",
            webhook_id=required["PAYPAL_WEBHOOK_ID"],
        )


class PayPalBillingService:
    token_endpoint = "/v1/oauth2/token"
    subscriptions_endpoint = "/v1/billing/subscriptions"
    plans_endpoint = "/v1/billing/plans"
    verify_webhook_endpoint = "/v1/notifications/verify-webhook-signature"

    def __init__(
        self,
        config: PayPalBillingConfig | None = None,
        *,
        http_client: httpx.AsyncClient | None = None,
    ):
        """用于初始化当前对象。"""
        self.config = config or PayPalBillingConfig.from_settings(settings)
        self.http_client = http_client or httpx.AsyncClient(timeout=15.0)

    async def create_subscription(self, *, user_id: int) -> dict[str, str]:
        """用于创建订阅。"""
        access_token = await self._fetch_access_token()
        try:
            response = await self.http_client.post(
                f"{self.config.api_base}{self.subscriptions_endpoint}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "PayPal-Request-Id": (f"user-{user_id}-plan-{self.config.plan_id}"),
                },
                json={
                    "plan_id": self.config.plan_id,
                    "application_context": {
                        "return_url": self.config.return_url,
                        "cancel_url": self.config.cancel_url,
                    },
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise PayPalBillingError("paypal_subscription_create_failed") from exc

        payload = response.json()
        subscription_id = self._required_string(payload, "id")
        approval_url = self._approval_url(payload)
        return {
            "provider": "paypal",
            "subscription_id": subscription_id,
            "status": str(payload.get("status") or ""),
            "approval_url": approval_url,
        }

    async def get_plan(self) -> dict[str, str]:
        """用于获取方案。"""
        access_token = await self._fetch_access_token()
        try:
            response = await self.http_client.get(
                f"{self.config.api_base}{self.plans_endpoint}/{self.config.plan_id}",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise PayPalBillingError("paypal_plan_fetch_failed") from exc

        payload = response.json()
        fixed_price = self._regular_fixed_price(payload)
        return {
            "id": self._required_string(payload, "id"),
            "name": str(payload.get("name") or ""),
            "price": self._required_nested_string(fixed_price, "value"),
            "currency_code": self._required_nested_string(fixed_price, "currency_code"),
        }

    async def get_subscription(self, *, subscription_id: str) -> dict[str, Any]:
        """用于获取订阅。"""
        access_token = await self._fetch_access_token()
        try:
            response = await self.http_client.get(
                f"{self.config.api_base}{self.subscriptions_endpoint}/{subscription_id}",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise PayPalBillingError("paypal_subscription_fetch_failed") from exc

        payload = response.json()
        return {
            "provider": "paypal",
            "subscription_id": self._required_string(payload, "id"),
            "status": self._required_string(payload, "status"),
            "raw_payload": payload,
        }

    async def cancel_subscription(
        self,
        *,
        subscription_id: str,
        reason: str = "User requested cancellation",
    ) -> None:
        """用于取消订阅。"""
        access_token = await self._fetch_access_token()
        try:
            response = await self.http_client.post(
                (
                    f"{self.config.api_base}{self.subscriptions_endpoint}/"
                    f"{subscription_id}/cancel"
                ),
                headers={"Authorization": f"Bearer {access_token}"},
                json={"reason": reason},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise PayPalBillingError("paypal_subscription_cancel_failed") from exc

    async def verify_webhook(
        self, *, headers: dict[str, str], event: dict[str, object]
    ) -> None:
        """用于校验webhook。"""
        access_token = await self._fetch_access_token()
        try:
            response = await self.http_client.post(
                f"{self.config.api_base}{self.verify_webhook_endpoint}",
                headers={"Authorization": f"Bearer {access_token}"},
                json={
                    "auth_algo": self._required_header(headers, "paypal-auth-algo"),
                    "cert_url": self._required_header(headers, "paypal-cert-url"),
                    "transmission_id": self._required_header(
                        headers, "paypal-transmission-id"
                    ),
                    "transmission_sig": self._required_header(
                        headers, "paypal-transmission-sig"
                    ),
                    "transmission_time": self._required_header(
                        headers, "paypal-transmission-time"
                    ),
                    "webhook_id": self.config.webhook_id,
                    "webhook_event": event,
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise PayPalBillingError("paypal_webhook_verification_failed") from exc

        if response.json().get("verification_status") != "SUCCESS":
            raise PayPalBillingError("paypal_webhook_signature_invalid")

    async def _fetch_access_token(self) -> str:
        """用于获取accesstoken。"""
        try:
            response = await self.http_client.post(
                f"{self.config.api_base}{self.token_endpoint}",
                auth=(self.config.client_id, self.config.client_secret),
                data={"grant_type": "client_credentials"},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise PayPalBillingError("paypal_token_failed") from exc
        return self._required_string(response.json(), "access_token")

    def _approval_url(self, payload: dict[str, object]) -> str:
        """用于处理批准地址。"""
        links = payload.get("links")
        if not isinstance(links, list):
            raise PayPalBillingError("paypal_approval_url_missing")
        for link in links:
            if not isinstance(link, dict):
                continue
            if link.get("rel") == "approve" and isinstance(link.get("href"), str):
                return str(link["href"])
        raise PayPalBillingError("paypal_approval_url_missing")

    def _required_string(self, payload: dict[str, object], field: str) -> str:
        """用于处理必填字符串。"""
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            raise PayPalBillingError(f"paypal_{field}_missing")
        return value

    def _regular_fixed_price(self, payload: dict[str, object]) -> dict[str, object]:
        """用于处理常规固定价格。"""
        billing_cycles = payload.get("billing_cycles")
        if not isinstance(billing_cycles, list):
            raise PayPalBillingError("paypal_plan_price_missing")
        for billing_cycle in billing_cycles:
            if not isinstance(billing_cycle, dict):
                continue
            if billing_cycle.get("tenure_type") != "REGULAR":
                continue
            pricing_scheme = billing_cycle.get("pricing_scheme")
            if not isinstance(pricing_scheme, dict):
                continue
            fixed_price = pricing_scheme.get("fixed_price")
            if isinstance(fixed_price, dict):
                return fixed_price
        raise PayPalBillingError("paypal_plan_price_missing")

    def _required_nested_string(self, payload: dict[str, object], field: str) -> str:
        """用于处理必填嵌套字符串。"""
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            raise PayPalBillingError(f"paypal_plan_{field}_missing")
        return value

    def _required_header(self, headers: dict[str, str], name: str) -> str:
        """用于处理必填头部。"""
        value = headers.get(name)
        if not value:
            raise PayPalBillingError(f"{name}_missing")
        return value
