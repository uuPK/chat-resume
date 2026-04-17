"""用于按需暴露 Agent 状态层的公共对象。"""

__all__ = ["AgentEvent", "AgentSession", "AgentSessionStore"]


def __getattr__(name: str):
    """用于延迟导入状态层对象，避免不必要的数据库依赖。"""
    if name in {"AgentEvent", "AgentSession"}:
        from .models import AgentEvent, AgentSession

        return {
            "AgentEvent": AgentEvent,
            "AgentSession": AgentSession,
        }[name]
    if name == "AgentSessionStore":
        from .store import AgentSessionStore

        return AgentSessionStore
    raise AttributeError(name)
