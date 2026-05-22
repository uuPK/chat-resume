"""用于按需暴露运行时层的公共对象。"""

__all__ = [
    "AgentDefinition",
    "AgentHarness",
    "ConfirmationSessionManager",
    "confirmation_manager",
]


def __getattr__(name: str):
    """用于延迟导入运行时对象，降低包初始化耦合。"""
    if name == "AgentDefinition":
        from .contracts import AgentDefinition

        return AgentDefinition
    if name == "AgentHarness":
        from .harness import AgentHarness

        return AgentHarness
    if name in {"ConfirmationSessionManager", "confirmation_manager"}:
        from .permissions import ConfirmationSessionManager, confirmation_manager

        return {
            "ConfirmationSessionManager": ConfirmationSessionManager,
            "confirmation_manager": confirmation_manager,
        }[name]
    raise AttributeError(name)
