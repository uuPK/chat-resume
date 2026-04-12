"""
Shared tool execution contracts.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    name: str
    description: str

    @abstractmethod
    def execute(self, input: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class ToolExecutor(ABC):
    @abstractmethod
    def execute(
        self,
        *,
        tool_name: str,
        tool_input: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        raise NotImplementedError
