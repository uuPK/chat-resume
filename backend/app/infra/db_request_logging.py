"""
数据库请求日志辅助模块。

按请求收集连接池 checkout 和 SQL 执行耗时，用于在慢请求日志中区分连接慢还是查询慢。
"""

from __future__ import annotations

import logging
from contextvars import ContextVar, Token
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RequestDBMetrics:
    """用于保存单个请求内的数据库访问耗时。"""

    checkout_count: int = 0
    checkout_ms_total: float = 0.0
    query_count: int = 0
    query_ms_total: float = 0.0
    longest_query_ms: float = 0.0
    longest_query_statement: str = ""


_request_metrics: ContextVar[RequestDBMetrics | None] = ContextVar(
    "request_db_metrics", default=None
)


def start_request_metrics() -> Token[RequestDBMetrics | None]:
    """用于在请求开始时初始化一份新的数据库耗时快照。"""
    return _request_metrics.set(RequestDBMetrics())


def get_request_metrics() -> RequestDBMetrics | None:
    """用于读取当前请求上下文中的数据库耗时快照。"""
    return _request_metrics.get()


def reset_request_metrics(token: Token[RequestDBMetrics | None]) -> None:
    """用于在请求结束后恢复上一个数据库耗时上下文。"""
    _request_metrics.reset(token)


def record_checkout(elapsed_ms: float) -> None:
    """用于记录连接取出耗时。"""
    metrics = _request_metrics.get()
    if metrics is None:
        return
    metrics.checkout_count += 1
    metrics.checkout_ms_total += elapsed_ms


def record_query(statement: str, elapsed_ms: float) -> None:
    """用于记录 SQL 执行耗时并输出慢查询日志。"""
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
            "db.query.slow",
            extra={
                "db_query_ms": round(elapsed_ms, 2),
                "db_query_sql": truncated_statement,
            },
        )


__all__ = [
    "RequestDBMetrics",
    "get_request_metrics",
    "record_checkout",
    "record_query",
    "reset_request_metrics",
    "start_request_metrics",
]
