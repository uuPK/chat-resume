"""Warning filters for noisy third-party startup output."""

from __future__ import annotations

import warnings

_ORIGINAL_SHOWWARNING = warnings.showwarning
_LANGGRAPH_ALLOWED_OBJECTS_WARNING = (
    "The default value of `allowed_objects` will change in a future version."
)


def _showwarning_without_langgraph_allowed_objects(
    message,
    category,
    filename,
    lineno,
    file=None,
    line=None,
) -> None:
    """用于过滤 LangGraph 启动时的已知 LangChain deprecation 噪声。"""
    if (
        "langgraph/checkpoint/serde/encrypted.py" in filename
        and _LANGGRAPH_ALLOWED_OBJECTS_WARNING in str(message)
    ):
        return
    _ORIGINAL_SHOWWARNING(
        message,
        category,
        filename,
        lineno,
        file=file,
        line=line,
    )


def suppress_noisy_dependency_warnings() -> None:
    """用于压制第三方依赖在启动阶段输出的已知无行动价值警告。"""
    warnings.filterwarnings(
        "ignore",
        message=(
            r"The default value of `allowed_objects` will change in a future version\."
        ),
        category=Warning,
    )
    warnings.showwarning = _showwarning_without_langgraph_allowed_objects
