"""用于覆盖 test_oauth_state_service.py 对应的回归测试。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services.auth.oauth_state_service import (
    OAuthStateError,
    OAuthStateService,
)


def test_generated_state_can_be_consumed_once():
    """用于验证generatedstatecanbeconsumed单次运行。"""
    now = datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc)
    service = OAuthStateService(clock=lambda: now)

    issued = service.issue_state()

    assert isinstance(issued.value, str)
    assert len(issued.value) >= 43
    service.consume_state(issued.value)

    with pytest.raises(OAuthStateError) as exc_info:
        service.consume_state(issued.value)

    assert exc_info.value.error_code == "invalid_state"


@pytest.mark.parametrize("raw_state", [None, ""])
def test_missing_state_is_rejected(raw_state):
    """用于验证missingstateisrejected。"""
    service = OAuthStateService()

    with pytest.raises(OAuthStateError) as exc_info:
        service.consume_state(raw_state)

    assert exc_info.value.error_code == "invalid_state"


def test_tampered_state_is_rejected():
    """用于验证tamperedstateisrejected。"""
    service = OAuthStateService()
    issued = service.issue_state()
    tampered_state = f"{issued.value}x"

    with pytest.raises(OAuthStateError) as exc_info:
        service.consume_state(tampered_state)

    assert exc_info.value.error_code == "invalid_state"


def test_expired_state_is_rejected():
    """用于验证expiredstateisrejected。"""
    current_time = datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc)
    service = OAuthStateService(
        expires_in=timedelta(minutes=10),
        clock=lambda: current_time,
    )
    issued = service.issue_state()

    current_time = current_time + timedelta(minutes=10, seconds=1)

    with pytest.raises(OAuthStateError) as exc_info:
        service.consume_state(issued.value)

    assert exc_info.value.error_code == "invalid_state"
