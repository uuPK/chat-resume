"""用于覆盖 test_google_oauth_client.py 对应的回归测试。"""

from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.services.auth.google_oauth_client import (
    GoogleOAuthAuthenticationError,
    GoogleOAuthClient,
    GoogleOAuthConfig,
    GoogleOAuthConfigurationError,
)


def test_google_oauth_client_builds_authorization_url():
    """用于验证GoogleOAuth客户端buildsauthorizationurl。"""
    client = GoogleOAuthClient(
        GoogleOAuthConfig(
            client_id="google-client-id",
            client_secret="google-client-secret",
            redirect_uri="http://localhost:8000/api/auth/google/callback",
        )
    )

    url = client.authorization_url(state="state-token")

    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == (
        "https://accounts.google.com/o/oauth2/v2/auth"
    )
    assert params["client_id"] == ["google-client-id"]
    assert params["redirect_uri"] == [
        "http://localhost:8000/api/auth/google/callback"
    ]
    assert params["response_type"] == ["code"]
    assert params["scope"] == ["openid email profile"]
    assert params["state"] == ["state-token"]


def test_google_oauth_config_requires_google_oauth_settings(monkeypatch):
    """用于验证GoogleOAuthconfigrequiresGoogleOAuth配置。"""
    from app.infra.config import settings

    monkeypatch.setattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "")
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", "secret")
    monkeypatch.setattr(
        settings,
        "GOOGLE_OAUTH_REDIRECT_URI",
        "http://localhost:8000/api/auth/google/callback",
    )

    with pytest.raises(GoogleOAuthConfigurationError) as exc_info:
        GoogleOAuthConfig.from_settings(settings)

    assert exc_info.value.error_code == "config_missing"
    assert "GOOGLE_OAUTH_CLIENT_ID" in str(exc_info.value)


@pytest.mark.asyncio
async def test_google_oauth_client_exchanges_code_for_tokens():
    """用于验证GoogleOAuth客户端exchangescodefortokens。"""
    seen_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        """用于处理handler。"""
        seen_requests.append(request)
        return httpx.Response(
            200,
            json={
                "access_token": "google-access-token",
                "expires_in": 3599,
                "id_token": "google-id-token",
                "refresh_token": "google-refresh-token",
                "scope": "openid email profile",
                "token_type": "Bearer",
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        client = GoogleOAuthClient(
            GoogleOAuthConfig(
                client_id="google-client-id",
                client_secret="google-client-secret",
                redirect_uri="http://localhost:8000/api/auth/google/callback",
            ),
            http_client=http_client,
        )

        tokens = await client.exchange_code("authorization-code")

    assert tokens.access_token == "google-access-token"
    assert tokens.token_type == "Bearer"
    assert tokens.id_token == "google-id-token"
    assert not hasattr(tokens, "refresh_token")
    assert len(seen_requests) == 1
    request = seen_requests[0]
    assert request.method == "POST"
    assert str(request.url) == "https://oauth2.googleapis.com/token"
    body = parse_qs(request.content.decode())
    assert body["grant_type"] == ["authorization_code"]
    assert body["code"] == ["authorization-code"]
    assert body["client_id"] == ["google-client-id"]
    assert body["client_secret"] == ["google-client-secret"]
    assert body["redirect_uri"] == [
        "http://localhost:8000/api/auth/google/callback"
    ]


@pytest.mark.asyncio
async def test_google_oauth_client_normalizes_token_exchange_errors():
    """用于验证GoogleOAuth客户端normalizes令牌exchangeerrors。"""
    def handler(request: httpx.Request) -> httpx.Response:
        """用于处理handler。"""
        return httpx.Response(
            400,
            json={"error": "invalid_grant", "error_description": "Bad code"},
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        client = GoogleOAuthClient(
            GoogleOAuthConfig(
                client_id="google-client-id",
                client_secret="google-client-secret",
                redirect_uri="http://localhost:8000/api/auth/google/callback",
            ),
            http_client=http_client,
        )

        with pytest.raises(GoogleOAuthAuthenticationError) as exc_info:
            await client.exchange_code("bad-code")

    assert exc_info.value.error_code == "google_exchange_failed"


@pytest.mark.asyncio
async def test_google_oauth_client_fetches_verified_identity():
    """用于验证GoogleOAuth客户端fetchesverifiedidentity。"""
    seen_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        """用于处理handler。"""
        seen_requests.append(request)
        return httpx.Response(
            200,
            json={
                "sub": "google-sub-123",
                "email": "user@example.com",
                "email_verified": True,
                "name": "Google User",
                "picture": "https://example.com/avatar.png",
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        client = GoogleOAuthClient(
            GoogleOAuthConfig(
                client_id="google-client-id",
                client_secret="google-client-secret",
                redirect_uri="http://localhost:8000/api/auth/google/callback",
            ),
            http_client=http_client,
        )

        identity = await client.fetch_identity("google-access-token")

    assert identity.sub == "google-sub-123"
    assert identity.email == "user@example.com"
    assert identity.email_verified is True
    assert identity.name == "Google User"
    assert identity.can_use_for_login is True
    assert not hasattr(identity, "access_token")
    assert not hasattr(identity, "refresh_token")
    request = seen_requests[0]
    assert str(request.url) == "https://openidconnect.googleapis.com/v1/userinfo"
    assert request.headers["Authorization"] == "Bearer google-access-token"


@pytest.mark.asyncio
async def test_google_oauth_client_marks_unverified_email_unusable():
    """用于验证GoogleOAuth客户端marksunverifiedemailunusable。"""
    def handler(request: httpx.Request) -> httpx.Response:
        """用于处理handler。"""
        return httpx.Response(
            200,
            json={
                "sub": "google-sub-123",
                "email": "user@example.com",
                "email_verified": False,
                "name": "Google User",
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        client = GoogleOAuthClient(
            GoogleOAuthConfig(
                client_id="google-client-id",
                client_secret="google-client-secret",
                redirect_uri="http://localhost:8000/api/auth/google/callback",
            ),
            http_client=http_client,
        )

        identity = await client.fetch_identity("google-access-token")

    assert identity.email_verified is False
    assert identity.can_use_for_login is False


@pytest.mark.asyncio
async def test_google_oauth_client_rejects_identity_without_required_fields():
    """用于验证GoogleOAuth客户端rejectsidentitywithoutrequiredfields。"""
    def handler(request: httpx.Request) -> httpx.Response:
        """用于处理handler。"""
        return httpx.Response(
            200,
            json={
                "email": "user@example.com",
                "email_verified": True,
                "name": "Google User",
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        client = GoogleOAuthClient(
            GoogleOAuthConfig(
                client_id="google-client-id",
                client_secret="google-client-secret",
                redirect_uri="http://localhost:8000/api/auth/google/callback",
            ),
            http_client=http_client,
        )

        with pytest.raises(GoogleOAuthAuthenticationError) as exc_info:
            await client.fetch_identity("google-access-token")

    assert exc_info.value.error_code == "google_exchange_failed"
