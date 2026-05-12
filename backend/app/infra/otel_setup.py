"""本地 OpenTelemetry trace 配置。"""

from __future__ import annotations

from contextlib import nullcontext
from typing import Any

from app.infra.config import settings

_configured = False
_tracer: Any | None = None


def configure_otel_tracing() -> bool:
    """用于按配置初始化 OTLP trace exporter。"""
    global _configured, _tracer
    if _configured:
        return _tracer is not None
    _configured = True
    if not settings.OTEL_TRACES_ENABLED:
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except Exception:
        _tracer = None
        return False

    resource = Resource.create(
        {
            "service.name": settings.OTEL_SERVICE_NAME,
            "deployment.environment": settings.APP_ENV,
        }
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_TRACES_ENDPOINT)
        )
    )
    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer("chat-resume")
    return True


def start_span(name: str, attributes: dict[str, Any] | None = None):
    """用于创建当前 trace span，未启用时返回空上下文。"""
    if _tracer is None:
        return nullcontext(None)
    return _tracer.start_as_current_span(name, attributes=attributes or {})


def record_exception(span: Any | None, exc: BaseException) -> None:
    """用于把异常信息写入当前 span。"""
    if span is None:
        return
    try:
        span.record_exception(exc)
        span.set_attribute("error", True)
    except Exception:
        return


def set_span_attribute(span: Any | None, key: str, value: Any) -> None:
    """用于安全写入 span attribute。"""
    if span is None:
        return
    try:
        span.set_attribute(key, value)
    except Exception:
        return


__all__ = [
    "configure_otel_tracing",
    "record_exception",
    "set_span_attribute",
    "start_span",
]
