from typing import Annotated, Literal, Sequence, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class InterviewState(TypedDict):
    """
    定义面试 Agent (Supervisor 架构) 的全局状态
    """
    # 消息记录，包含系统 Prompt，工具调用和多轮对话。使用 add_messages 自动追加
    messages: Annotated[Sequence[BaseMessage], add_messages]

    # 候选人当前的技能画像打分情况
    skill_matrix: dict[str, int]

    # 下一个要流转到的节点名称
    next_node: Literal["Tech_Expert", "HR_Expert", "Evaluator", "FINISH"]

    # 当前所处的面试阶段
    stage: Literal["opening", "deep_dive", "behavioral", "closing"]
