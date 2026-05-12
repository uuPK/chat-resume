"""LogQL 和 PromQL 查询服务。"""

from __future__ import annotations

from typing import Any

import httpx

from app.infra.config import settings


class ObservabilityQueryService:
    """用于访问本地 Loki 和 Prometheus 查询 API。"""

    def __init__(
        self,
        *,
        loki_base_url: str | None = None,
        prometheus_base_url: str | None = None,
        timeout_seconds: float | None = None,
        client: httpx.Client | None = None,
    ):
        """用于注入查询端点和测试客户端。"""
        self.loki_base_url = (loki_base_url or settings.LOKI_BASE_URL).rstrip("/")
        self.prometheus_base_url = (
            prometheus_base_url or settings.PROMETHEUS_BASE_URL
        ).rstrip("/")
        self.timeout_seconds = timeout_seconds or settings.OBSERVABILITY_QUERY_TIMEOUT_SECONDS
        self.client = client

    def query_promql(self, query: str, *, time: str | None = None) -> dict[str, Any]:
        """用于执行一次 PromQL instant query。"""
        normalized_query = _required_query(query)
        params: dict[str, Any] = {"query": normalized_query}
        if time:
            params["time"] = time
        payload = self._get_json(
            f"{self.prometheus_base_url}/api/v1/query",
            params=params,
        )
        if payload.get("success") is False:
            return payload
        data = _successful_data(payload)
        return {
            "success": True,
            "source": "prometheus",
            "query": normalized_query,
            "result_type": data.get("resultType"),
            "results": data.get("result", []),
        }

    def query_logql(
        self,
        query: str,
        *,
        limit: int = 20,
        start: str | None = None,
        end: str | None = None,
    ) -> dict[str, Any]:
        """用于执行一次 Loki LogQL range query。"""
        normalized_query = _required_query(query)
        safe_limit = max(1, min(int(limit or 20), 100))
        params: dict[str, Any] = {
            "query": normalized_query,
            "limit": safe_limit,
            "direction": "backward",
        }
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        payload = self._get_json(
            f"{self.loki_base_url}/loki/api/v1/query_range",
            params=params,
        )
        if payload.get("success") is False:
            return payload
        data = _successful_data(payload)
        return {
            "success": True,
            "source": "loki",
            "query": normalized_query,
            "limit": safe_limit,
            "result_type": data.get("resultType"),
            "results": data.get("result", []),
        }

    def _get_json(self, url: str, *, params: dict[str, Any]) -> dict[str, Any]:
        """用于执行 HTTP GET 并返回 JSON 响应。"""
        try:
            if self.client is not None:
                response = self.client.get(url, params=params)
            else:
                response = httpx.get(url, params=params, timeout=self.timeout_seconds)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            return {
                "success": False,
                "error": {
                    "type": "observability_query_failed",
                    "message": str(exc),
                    "recoverable": True,
                },
            }
        return payload if isinstance(payload, dict) else {}


def _required_query(query: str) -> str:
    """用于校验查询语句不能为空。"""
    normalized = str(query or "").strip()
    if not normalized:
        raise ValueError("query 不能为空")
    return normalized


def _successful_data(payload: dict[str, Any]) -> dict[str, Any]:
    """用于解析 Loki/Prometheus 的 success 响应。"""
    if not payload.get("success", True):
        return {}
    if payload.get("status") == "success":
        data = payload.get("data")
        return data if isinstance(data, dict) else {}
    error = payload.get("error") or payload.get("errorType") or "query failed"
    raise ValueError(str(error))


__all__ = ["ObservabilityQueryService"]
