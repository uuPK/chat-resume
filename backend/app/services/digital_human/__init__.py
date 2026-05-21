"""数字人供应商服务入口。"""

from .volcengine_service import (
    VolcengineConfigurationError,
    VolcengineVoiceService,
)

__all__ = [
    "VolcengineConfigurationError",
    "VolcengineVoiceService",
]
