"""用于暴露结构化面试 Agent 相关能力。"""

__all__ = ["InterviewerAgent"]


def __getattr__(name: str):
    """用于按需加载面试 Agent，避免包初始化时引入重依赖。"""
    if name == "InterviewerAgent":
        from .agent import InterviewerAgent

        return InterviewerAgent
    raise AttributeError(name)
