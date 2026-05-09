"""Helpers for scoping LangSmith traces around agent runs."""

from __future__ import annotations

import logging
from typing import Any

from app.infra.config import settings
from app.infra.langsmith_setup import get_langsmith_client

logger = logging.getLogger(__name__)


class LangSmithRunObserver:
    """用于给 Deep Agents 的原生 LangSmith trace 附加项目、标签和元数据。"""

    def __init__(
        self,
        *,
        run_id: str,
        agent_type: str,
        run_kind: str,
        user_id: int,
        input_text: str | None,
        metadata: dict[str, Any] | None = None,
    ):
        self.client = get_langsmith_client()
        self.run_id = run_id
        self.agent_type = agent_type
        self.run_kind = run_kind
        self.user_id = user_id
        self.input_text = input_text
        self.metadata = {
            "run_id": run_id,
            "agent_type": agent_type,
            "run_kind": run_kind,
            "user_id": user_id,
            "environment": settings.APP_ENV,
            **(metadata or {}),
        }
        self.tags = [
            "agent",
            f"agent:{agent_type}",
            f"kind:{run_kind}",
            f"env:{settings.APP_ENV}",
        ]
        self._trace_context: Any | None = None

    @property
    def enabled(self) -> bool:
        return self.client is not None

    def __enter__(self) -> "LangSmithRunObserver":
        if not self.enabled:
            return self
        try:
            from langsmith import tracing_context

            self._trace_context = tracing_context(
                project_name=settings.LANGSMITH_PROJECT,
                tags=self.tags,
                metadata=self.metadata,
                enabled=True,
                client=self.client,
            )
            self._trace_context.__enter__()
        except Exception as exc:
            logger.warning(
                "LangSmith run start failed run_id=%s error=%s",
                self.run_id,
                exc,
            )
            self._trace_context = None
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._trace_context is None:
            return
        try:
            self._trace_context.__exit__(exc_type, exc, tb)
        except Exception as exit_exc:
            logger.warning(
                "LangSmith tracing context exit failed run_id=%s error=%s",
                self.run_id,
                exit_exc,
            )

    def finish(self, output: Any, *, metadata: dict[str, Any] | None = None) -> None:
        del output, metadata

    def fail(self, error: str, *, metadata: dict[str, Any] | None = None) -> None:
        del error, metadata

    def on_runtime_event(self, event: dict[str, Any]) -> None:
        del event
