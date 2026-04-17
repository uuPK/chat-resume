"""用于定义工具层共享的抽象协议。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """用于约束单个工具应提供的最小能力。"""

    name: str
    description: str

    @abstractmethod
    def execute(self, input: dict[str, Any]) -> dict[str, Any]:
        """用于执行单个工具的核心逻辑。"""
        raise NotImplementedError


class ToolExecutor(ABC):
    """用于约束 runtime 调用工具时的统一入口。"""

    @abstractmethod
    def execute(
        self,
        *,
        tool_name: str,
        tool_input: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """用于根据工具名和上下文执行一次工具调用。"""
        raise NotImplementedError
