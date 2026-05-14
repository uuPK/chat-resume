"""测试 OpenRouter 指数退避重试逻辑。"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.runtime.pi_agent_openrouter import (
    OpenRouterCircuitOpenError,
    OpenRouterHTTPError,
    _is_retryable_status,
    _pump_with_retry,
    _retry_wait,
    _reset_openrouter_circuit_breaker,
)


# ---------------------------------------------------------------------------
# 单元测试：辅助函数
# ---------------------------------------------------------------------------


def test_retry_wait_uses_retry_after_when_provided():
    """Retry-After header 存在时应优先使用该值。"""
    wait = _retry_wait(attempt=0, retry_after=5.0)
    assert wait == 5.0


def test_retry_wait_caps_at_max():
    """Retry-After 超出上限时应被截断到 max_wait。"""
    wait = _retry_wait(attempt=0, retry_after=999.0)
    assert wait == 30.0


def test_retry_wait_exponential_without_retry_after():
    """无 Retry-After 时等待时间应在 [base*2^attempt, base*2^attempt + 1 + max_wait] 范围内。"""
    wait = _retry_wait(attempt=1, retry_after=None)
    # base=1, 2^1=2, jitter in [0,1) → 期望 2.0 ~ 3.0
    assert 2.0 <= wait < 4.0


def test_is_retryable_status_true():
    """429/502/503/504 应被视为可重试。"""
    for code in (429, 502, 503, 504):
        assert _is_retryable_status(code) is True


def test_is_retryable_status_false():
    """400/401/403/500 不应触发重试。"""
    for code in (400, 401, 403, 500):
        assert _is_retryable_status(code) is False


# ---------------------------------------------------------------------------
# 集成测试：_pump_with_retry 行为
# ---------------------------------------------------------------------------


def _make_args():
    """构造调用 _pump_with_retry 所需的最简 mock 参数。"""
    model = MagicMock()
    context = MagicMock()
    options = MagicMock()
    partial = MagicMock()
    queue: asyncio.Queue = asyncio.Queue()
    return model, context, options, partial, queue


@pytest.mark.asyncio
async def test_429_retry_then_success():
    """429 后重试，第二次成功，最终不抛出异常。"""
    model, context, options, partial, queue = _make_args()
    call_count = 0

    async def fake_pump(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise OpenRouterHTTPError(status_code=429, message="rate limited")

    with patch(
        "app.runtime.pi_agent_openrouter._pump_openrouter_stream",
        side_effect=fake_pump,
    ), patch(
        "app.runtime.pi_agent_openrouter.settings",
        OPENROUTER_MAX_RETRIES=3,
        OPENROUTER_CIRCUIT_BREAKER_ENABLED=False,
    ), patch(
        "asyncio.sleep",
        new_callable=AsyncMock,
    ):
        await _pump_with_retry(model, context, options, partial, queue)

    assert call_count == 2


@pytest.mark.asyncio
async def test_503_all_retries_exhausted_raises():
    """503 连续失败超过最大重试次数后应抛出最后一次异常。"""
    model, context, options, partial, queue = _make_args()

    async def fake_pump(*args, **kwargs):
        raise OpenRouterHTTPError(status_code=503, message="service unavailable")

    with patch(
        "app.runtime.pi_agent_openrouter._pump_openrouter_stream",
        side_effect=fake_pump,
    ), patch(
        "app.runtime.pi_agent_openrouter.settings",
        OPENROUTER_MAX_RETRIES=3,
        OPENROUTER_CIRCUIT_BREAKER_ENABLED=False,
    ), patch(
        "asyncio.sleep",
        new_callable=AsyncMock,
    ):
        with pytest.raises(OpenRouterHTTPError) as exc_info:
            await _pump_with_retry(model, context, options, partial, queue)

    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_429_with_retry_after_header_uses_header_value():
    """429 含 Retry-After 时应以 header 值作为等待时间。"""
    model, context, options, partial, queue = _make_args()
    call_count = 0
    sleep_calls: list[float] = []

    async def fake_pump(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise OpenRouterHTTPError(status_code=429, message="rate limited", retry_after=7.0)

    async def fake_sleep(seconds: float):
        sleep_calls.append(seconds)

    with patch(
        "app.runtime.pi_agent_openrouter._pump_openrouter_stream",
        side_effect=fake_pump,
    ), patch(
        "app.runtime.pi_agent_openrouter.settings",
        OPENROUTER_MAX_RETRIES=3,
        OPENROUTER_CIRCUIT_BREAKER_ENABLED=False,
    ), patch(
        "asyncio.sleep",
        side_effect=fake_sleep,
    ):
        await _pump_with_retry(model, context, options, partial, queue)

    assert len(sleep_calls) == 1
    assert sleep_calls[0] == 7.0


@pytest.mark.asyncio
async def test_400_non_retryable_raises_immediately():
    """400 不属于可重试状态码，应立即抛出，不进行任何重试。"""
    model, context, options, partial, queue = _make_args()
    call_count = 0

    async def fake_pump(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise OpenRouterHTTPError(status_code=400, message="bad request")

    with patch(
        "app.runtime.pi_agent_openrouter._pump_openrouter_stream",
        side_effect=fake_pump,
    ), patch(
        "app.runtime.pi_agent_openrouter.settings",
        OPENROUTER_MAX_RETRIES=3,
        OPENROUTER_CIRCUIT_BREAKER_ENABLED=False,
    ), patch(
        "asyncio.sleep",
        new_callable=AsyncMock,
    ):
        with pytest.raises(OpenRouterHTTPError) as exc_info:
            await _pump_with_retry(model, context, options, partial, queue)

    assert call_count == 1
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_connect_error_retried():
    """httpx.ConnectError 应触发重试，最终全部失败时抛出。"""
    model, context, options, partial, queue = _make_args()
    call_count = 0

    async def fake_pump(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise httpx.ConnectError("connection refused")

    with patch(
        "app.runtime.pi_agent_openrouter._pump_openrouter_stream",
        side_effect=fake_pump,
    ), patch(
        "app.runtime.pi_agent_openrouter.settings",
        OPENROUTER_MAX_RETRIES=2,
        OPENROUTER_CIRCUIT_BREAKER_ENABLED=False,
    ), patch(
        "asyncio.sleep",
        new_callable=AsyncMock,
    ):
        with pytest.raises(httpx.ConnectError):
            await _pump_with_retry(model, context, options, partial, queue)

    # 初始 1 次 + 2 次重试 = 3 次总调用
    assert call_count == 3


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_repeated_failures():
    """连续请求失败达到阈值后应快速失败，不再调用 OpenRouter。"""
    _reset_openrouter_circuit_breaker()
    model, context, options, partial, queue = _make_args()
    call_count = 0

    async def fake_pump(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise OpenRouterHTTPError(status_code=503, message="service unavailable")

    with patch(
        "app.runtime.pi_agent_openrouter._pump_openrouter_stream",
        side_effect=fake_pump,
    ), patch(
        "app.runtime.pi_agent_openrouter.settings",
        OPENROUTER_MAX_RETRIES=0,
        OPENROUTER_CIRCUIT_BREAKER_ENABLED=True,
        OPENROUTER_CIRCUIT_BREAKER_FAILURE_THRESHOLD=2,
        OPENROUTER_CIRCUIT_BREAKER_COOLDOWN_SECONDS=60,
    ), patch(
        "asyncio.sleep",
        new_callable=AsyncMock,
    ):
        for _ in range(2):
            with pytest.raises(OpenRouterHTTPError):
                await _pump_with_retry(model, context, options, partial, queue)

        with pytest.raises(OpenRouterCircuitOpenError):
            await _pump_with_retry(model, context, options, partial, queue)

    assert call_count == 2


@pytest.mark.asyncio
async def test_circuit_breaker_allows_probe_after_cooldown():
    """open 冷却期结束后应允许一次探测请求，成功后恢复 closed。"""
    _reset_openrouter_circuit_breaker()
    model, context, options, partial, queue = _make_args()
    call_count = 0
    now = 1000.0

    async def fake_pump(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise OpenRouterHTTPError(status_code=503, message="service unavailable")

    with patch(
        "app.runtime.pi_agent_openrouter._pump_openrouter_stream",
        side_effect=fake_pump,
    ), patch(
        "app.runtime.pi_agent_openrouter.settings",
        OPENROUTER_MAX_RETRIES=0,
        OPENROUTER_CIRCUIT_BREAKER_ENABLED=True,
        OPENROUTER_CIRCUIT_BREAKER_FAILURE_THRESHOLD=2,
        OPENROUTER_CIRCUIT_BREAKER_COOLDOWN_SECONDS=60,
    ), patch(
        "app.runtime.pi_agent_openrouter.monotonic",
        side_effect=lambda: now,
    ), patch(
        "asyncio.sleep",
        new_callable=AsyncMock,
    ):
        for _ in range(2):
            with pytest.raises(OpenRouterHTTPError):
                await _pump_with_retry(model, context, options, partial, queue)

        with pytest.raises(OpenRouterCircuitOpenError):
            await _pump_with_retry(model, context, options, partial, queue)

        now = 1061.0
        await _pump_with_retry(model, context, options, partial, queue)
        await _pump_with_retry(model, context, options, partial, queue)

    assert call_count == 4
