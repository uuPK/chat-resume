"""请求失败观测链路的集成测试。"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from types import SimpleNamespace

from fastapi import Request
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.infra.config import settings
from app.main import app

_FAILURE_PATH = "/api/_observability-test/fail"
_USER_FAILURE_PATH = "/api/_observability-test/user-fail"


def _install_failure_route() -> None:
    """安装仅用于测试的失败端点，避免污染生产路由代码。"""
    existing_paths = {getattr(route, "path", None) for route in app.router.routes}

    if _FAILURE_PATH not in existing_paths:

        @app.get(_FAILURE_PATH)
        async def _observability_failure_endpoint(candidate_id: str):
            """用于触发未处理异常并验证请求观测上下文。"""
            raise RuntimeError(f"candidate {candidate_id} exploded")

    if _USER_FAILURE_PATH not in existing_paths:

        @app.get(_USER_FAILURE_PATH)
        async def _observability_user_failure_endpoint(request: Request):
            """用于模拟已鉴权用户请求在业务层抛出异常。"""
            request.state.current_user = SimpleNamespace(id=7)
            raise RuntimeError("user scoped failure")


_install_failure_route()


def test_unhandled_error_response_and_log_share_debug_context(caplog):
    """未处理异常应该返回 request_id，并记录足够定位的错误上下文。"""
    request_id = "req-observe-123"
    client = TestClient(app, raise_server_exceptions=False)

    with caplog.at_level(logging.ERROR, logger="app.main"):
        response = client.get(
            f"{_FAILURE_PATH}?candidate_id=42&access_token=secret",
            headers={"X-Request-ID": request_id},
        )

    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == request_id
    assert response.json() == {
        "detail": "Internal server error",
        "request_id": request_id,
    }

    failed_records = [
        record for record in caplog.records if record.message == "request.failed"
    ]
    assert len(failed_records) == 1

    record = failed_records[0]
    assert record.request_id == request_id
    assert record.http_method == "GET"
    assert record.http_path == _FAILURE_PATH
    assert record.http_route == _FAILURE_PATH
    assert record.http_status == 500
    assert record.error_type == "RuntimeError"
    assert record.user_id == "-"
    assert record.release == (settings.SENTRY_RELEASE or "-")
    assert record.query_params == {
        "access_token": "[REDACTED]",
        "candidate_id": "42",
    }


def test_unhandled_error_log_includes_authenticated_user_id(caplog):
    """已鉴权请求失败时，错误日志应该带上当前用户 ID。"""
    request_id = "req-user-observe-123"
    client = TestClient(app, raise_server_exceptions=False)

    with caplog.at_level(logging.ERROR, logger="app.main"):
        response = client.get(
            _USER_FAILURE_PATH,
            headers={"X-Request-ID": request_id},
        )

    assert response.status_code == 500

    failed_records = [
        record for record in caplog.records if record.message == "request.failed"
    ]
    assert len(failed_records) == 1
    assert failed_records[0].request_id == request_id
    assert failed_records[0].user_id == "7"
