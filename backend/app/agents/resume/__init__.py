"""用于暴露简历优化 Agent 相关能力。"""

__all__ = ["ResumeAgent", "ResumeToolExecutor"]


def __getattr__(name: str):
    """用于按需加载简历 Agent，避免包初始化时引入重依赖。"""
    if name == "ResumeAgent":
        from .agent import ResumeAgent

        return ResumeAgent
    if name == "ResumeToolExecutor":
        from .executor import ResumeToolExecutor

        return ResumeToolExecutor
    raise AttributeError(name)
