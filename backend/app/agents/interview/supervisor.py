from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import Literal

from app.agents.interview.state import InterviewState
from app.agents.interview.llm import get_deepseek_llm

class RouteDecision(BaseModel):
    next_node: Literal["Tech_Expert", "HR_Expert", "FINISH"] = Field(
        description="决定下一个接管对话的节点名称。"
    )
    reasoning: str = Field(
        description="做出该路由决策的内心独白（Glass-box 呈现用）。"
    )

async def supervisor_node(state: InterviewState) -> dict:
    """
    Supervisor (面试主管) 节点：统筹全局，不直接提问，只负责状态流转。
    """
    # 调度大脑使用 deepseek-chat
    llm = get_deepseek_llm("deepseek-chat")
    structured_llm = llm.with_structured_output(RouteDecision, method="function_calling")

    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是这场硅谷级别技术面试的主管 (Supervisor)。
你的核心职责是像一个真实的大厂面试官一样，把控面试流程和节奏。
你的团队里有三个节点：
1. Tech_Expert (技术考官)：负责深度挖掘候选人的简历项目经验，以及考察核心的基础知识（八股文）。
2. HR_Expert (行为考官)：负责考察候选人的沟通能力、团队协作、抗压能力以及职业规划（Behavioral Questions）。
3. Evaluator (后台裁判)：负责在后台默默给候选人刚才的回答打分，不与候选人对话。（注意：Evaluator 会在候选人说话后自动执行，你无需手动路由给它）

【严格路由规则】
1. 你的职责是在 Tech_Expert 和 HR_Expert 之间选择，或者结束面试。
2. 面试刚开始时，必须交给 Tech_Expert 进行技术考察。
3. 技术面试环节必须足够充分。Tech_Expert 需要进行至少 6-8 轮以上的深度交流（包含项目深挖和基础八股文考察）。只有当技术考点已经考察得非常全面，或者候选人的技术能力已经展现得十分清晰后，才允许转给 HR_Expert。
4. 如果面试已经进入 HR 行为面试阶段，请持续交由 HR_Expert 提问，直到 HR 阶段也考察充分。
5. 如果候选人明确表示想结束面试，或者双方已经走完了完整的技术和 HR 流程并做完了反问环节，输出 FINISH。
请严格输出 JSON 格式的结果。
"""),
        # 使用 placeholder 注入之前的全部对话
        ("placeholder", "{messages}"),
        ("system", "请根据上文的对话记录，决定下一步把控制权交给谁。")
    ])

    chain = prompt | structured_llm
    decision: RouteDecision = await chain.ainvoke({"messages": state["messages"]})

    return {"next_node": decision.next_node}
