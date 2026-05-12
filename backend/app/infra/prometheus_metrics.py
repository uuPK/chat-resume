"""本地 Prometheus 指标导出工具。"""

from __future__ import annotations

from collections import defaultdict
from threading import Lock
from typing import Iterable

_HTTP_DURATION_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)
_lock = Lock()
_http_requests: dict[tuple[str, str, str], int] = defaultdict(int)
_http_duration_sum: dict[tuple[str, str], float] = defaultdict(float)
_http_duration_count: dict[tuple[str, str], int] = defaultdict(int)
_http_duration_buckets: dict[tuple[str, str, float], int] = defaultdict(int)
_db_query_count: dict[tuple[str], int] = defaultdict(int)
_db_query_duration_sum: dict[tuple[str], float] = defaultdict(float)


def record_http_request(
    *,
    method: str,
    path: str,
    status: int,
    duration_seconds: float,
    db_query_count: int = 0,
    db_query_duration_seconds: float = 0.0,
) -> None:
    """用于记录一次 HTTP 请求和该请求内的数据库查询指标。"""
    method_label = method.upper()
    status_label = str(status)
    path_label = path or "unknown"
    with _lock:
        _http_requests[(method_label, path_label, status_label)] += 1
        _http_duration_sum[(method_label, path_label)] += duration_seconds
        _http_duration_count[(method_label, path_label)] += 1
        for bucket in _HTTP_DURATION_BUCKETS:
            if duration_seconds <= bucket:
                _http_duration_buckets[(method_label, path_label, bucket)] += 1
        if db_query_count:
            _db_query_count[(path_label,)] += db_query_count
            _db_query_duration_sum[(path_label,)] += db_query_duration_seconds


def render_metrics() -> str:
    """用于把内存指标渲染成 Prometheus text exposition 格式。"""
    with _lock:
        request_items = dict(_http_requests)
        duration_sum_items = dict(_http_duration_sum)
        duration_count_items = dict(_http_duration_count)
        bucket_items = dict(_http_duration_buckets)
        db_count_items = dict(_db_query_count)
        db_duration_items = dict(_db_query_duration_sum)

    lines = [
        "# HELP chat_resume_http_requests_total Total HTTP requests.",
        "# TYPE chat_resume_http_requests_total counter",
    ]
    for labels, value in sorted(request_items.items()):
        method, path, status = labels
        lines.append(
            "chat_resume_http_requests_total"
            f"{_labels(method=method, path=path, status=status)} {value}"
        )

    lines.extend(
        [
            "# HELP chat_resume_http_request_duration_seconds HTTP request duration.",
            "# TYPE chat_resume_http_request_duration_seconds histogram",
        ]
    )
    duration_keys = sorted(duration_count_items)
    for method, path in duration_keys:
        for bucket in _HTTP_DURATION_BUCKETS:
            cumulative = bucket_items.get((method, path, bucket), 0)
            lines.append(
                "chat_resume_http_request_duration_seconds_bucket"
                f"{_labels(method=method, path=path, le=_bucket_label(bucket))} "
                f"{cumulative}"
            )
        total_count = duration_count_items[(method, path)]
        lines.append(
            "chat_resume_http_request_duration_seconds_bucket"
            f"{_labels(method=method, path=path, le='+Inf')} {total_count}"
        )
        lines.append(
            "chat_resume_http_request_duration_seconds_sum"
            f"{_labels(method=method, path=path)} "
            f"{duration_sum_items.get((method, path), 0.0):.6f}"
        )
        lines.append(
            "chat_resume_http_request_duration_seconds_count"
            f"{_labels(method=method, path=path)} {total_count}"
        )

    lines.extend(
        [
            "# HELP chat_resume_db_queries_total Total SQL queries inside requests.",
            "# TYPE chat_resume_db_queries_total counter",
        ]
    )
    for (path,), value in sorted(db_count_items.items()):
        lines.append(f"chat_resume_db_queries_total{_labels(path=path)} {value}")

    lines.extend(
        [
            "# HELP chat_resume_db_query_duration_seconds_total SQL duration inside requests.",
            "# TYPE chat_resume_db_query_duration_seconds_total counter",
        ]
    )
    for (path,), value in sorted(db_duration_items.items()):
        lines.append(
            "chat_resume_db_query_duration_seconds_total"
            f"{_labels(path=path)} {value:.6f}"
        )

    return "\n".join(lines) + "\n"


def reset_metrics_for_tests() -> None:
    """用于测试隔离时清空所有内存指标。"""
    with _lock:
        for metric in _metric_maps():
            metric.clear()


def _metric_maps() -> Iterable[dict]:
    """用于集中列出需要清空的内存指标容器。"""
    return (
        _http_requests,
        _http_duration_sum,
        _http_duration_count,
        _http_duration_buckets,
        _db_query_count,
        _db_query_duration_sum,
    )


def _labels(**items: str) -> str:
    """用于生成 Prometheus label 文本。"""
    encoded = [f'{key}="{_escape_label(value)}"' for key, value in items.items()]
    return "{" + ",".join(encoded) + "}"


def _escape_label(value: str) -> str:
    """用于转义 Prometheus label value。"""
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _bucket_label(bucket: float) -> str:
    """用于稳定输出 histogram bucket 边界。"""
    return f"{bucket:g}"


__all__ = ["record_http_request", "render_metrics", "reset_metrics_for_tests"]
