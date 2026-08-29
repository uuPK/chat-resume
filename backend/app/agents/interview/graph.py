from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from app.agents.interview.state import InterviewState
from app.agents.interview.supervisor import supervisor_node
from app.agents.interview.experts import tech_expert_node, hr_expert_node, evaluator_node
from app.agents.interview.tools import query_graph_rag, search_question_bank

def route_from_supervisor(state: InterviewState):
    """根据 Supervisor 的决策返回下一个边的名字"""
    next_node = state.get("next_node", "Tech_Expert")
    if next_node == "FINISH":
        return END
    return next_node

def route_after_expert(state: InterviewState):
    """
    专家提问完之后，如果模型调用了工具，则走向 ToolNode；
    如果模型直接生成了对用户的回复（提问），则走向结束本轮。
    """
    messages = state.get("messages", [])
    if not messages:
        return END

    last_message = messages[-1]
    # 判断是否包含工具调用
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"

    # 没有工具调用，说明专家的话术生成完毕，本轮图执行结束（等待下一次人类输入）
    return END

def create_interview_graph():
    """
    构建并编译带状态的主控制流图。
    """
    builder = StateGraph(InterviewState)

    # 1. 注册所有的 Node
    builder.add_node("Supervisor", supervisor_node)
    builder.add_node("Tech_Expert", tech_expert_node)
    builder.add_node("HR_Expert", hr_expert_node)
    builder.add_node("Evaluator", evaluator_node)

    # 注册 Tool Node
    builder.add_node("tools", ToolNode([query_graph_rag, search_question_bank]))

    # 2. 注册 Edges (流转逻辑)
    # 当用户说了一句话进来时，先走 Evaluator 进行内部打分
    builder.set_entry_point("Evaluator")

    # 评分结束后，走 Supervisor 进行路由
    builder.add_edge("Evaluator", "Supervisor")

    # Supervisor 根据状态决定调用哪个专家
    builder.add_conditional_edges(
        "Supervisor",
        route_from_supervisor,
        {"Tech_Expert": "Tech_Expert", "HR_Expert": "HR_Expert", END: END}
    )

    # 专家节点执行完后，判断是用了工具还是直接输出
    builder.add_conditional_edges(
        "Tech_Expert",
        route_after_expert,
        {"tools": "tools", END: END}
    )
    builder.add_conditional_edges(
        "HR_Expert",
        route_after_expert,
        {"tools": "tools", END: END}
    )

    # 如果调用了工具，工具返回结果后再次交还给原专家（假设为了简化，全交还给 Tech_Expert）
    builder.add_edge("tools", "Tech_Expert")

    # 3. 编译图，挂载 Checkpointer 以支持带记忆的流式对话
    checkpointer = MemorySaver()
    graph = builder.compile(checkpointer=checkpointer)

    return graph

# 导出供外部 FastAPI 路由调用
interview_agent = create_interview_graph()
