"""LogQL 和 PromQL 只读查询工具。"""

from __future__ import annotations

from typing import Any

from app.services.observability import ObservabilityQueryService


def query_metrics_promql(
    _resume_content: dict[str, Any],
    query: str,
    time: str | None = None,
) -> dict[str, Any]:
    """用于让 Agent 查询本地 Prometheus 指标。"""
    try:
        return ObservabilityQueryService().query_promql(query, time=time)
    except Exception as exc:
        return _tool_error(exc)


def query_logs_logql(
    _resume_content: dict[str, Any],
    query: str,
    limit: int = 20,
    start: str | None = None,
    end: str | None = None,
) -> dict[str, Any]:
    """用于让 Agent 查询本地 Loki 日志。"""
    try:
        return ObservabilityQueryService().query_logql(
            query,
            limit=limit,
            start=start,
            end=end,
        )
    except Exception as exc:
        return _tool_error(exc)


def _tool_error(exc: Exception) -> dict[str, Any]:
    """用于把查询异常转换成工具可恢复错误。"""
    return {
        "success": False,
        "error": {
            "type": "observability_query_failed",
            "message": str(exc),
            "recoverable": True,
        },
        "message": str(exc),
    }


__all__ = ["query_logs_logql", "query_metrics_promql"]
