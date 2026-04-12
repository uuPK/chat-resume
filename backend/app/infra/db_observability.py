"""
数据库可观测性工具。

按请求收集连接池 checkout 和 SQL 执行耗时，帮助区分连接慢还是查询慢。
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RequestDBMetrics:
    checkout_count: int = 0
    checkout_ms_total: float = 0.0
    query_count: int = 0
    query_ms_total: float = 0.0
    longest_query_ms: float = 0.0
    longest_query_statement: str = ""


_request_metrics: ContextVar[RequestDBMetrics | None] = ContextVar(
    "request_db_metrics", default=None
)


def start_request_metrics() -> object:
    return _request_metrics.set(RequestDBMetrics())


def get_request_metrics() -> RequestDBMetrics | None:
    return _request_metrics.get()


def reset_request_metrics(token: object) -> None:
    _request_metrics.reset(token)


def record_checkout(elapsed_ms: float) -> None:
    metrics = _request_metrics.get()
    if metrics is None:
        return
    metrics.checkout_count += 1
    metrics.checkout_ms_total += elapsed_ms


def record_query(statement: str, elapsed_ms: float) -> None:
    metrics = _request_metrics.get()
    if metrics is None:
        return

    normalized_statement = " ".join(statement.split())
    truncated_statement = normalized_statement[:240]

    metrics.query_count += 1
    metrics.query_ms_total += elapsed_ms
    if elapsed_ms >= metrics.longest_query_ms:
        metrics.longest_query_ms = elapsed_ms
        metrics.longest_query_statement = truncated_statement

    if elapsed_ms >= 200:
        logger.warning(
            "db query slow query_ms=%.2f sql=%s",
            elapsed_ms,
            truncated_statement,
        )
