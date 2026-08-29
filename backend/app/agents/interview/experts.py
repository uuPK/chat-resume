from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage
from app.agents.interview.state import InterviewState
from app.agents.interview.llm import get_deepseek_llm
from app.agents.interview.tools import query_graph_rag, search_question_bank
from pydantic import BaseModel, Field

async def tech_expert_node(state: InterviewState) -> dict:
    """
    技术考官 (Actor)。负责提问技术深度细节，可以使用工具。
    """
    # 技术考官为了深挖，我们暂时用 flash 速度快。如果是超高难度可切 v4-pro。
    llm = get_deepseek_llm("deepseek-chat")

    # 赋予考官事实核查和知识图谱检索的能力
    tools = [query_graph_rag, search_question_bank]
    llm_with_tools = llm.bind_tools(tools)

    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是这场硅谷级别技术面试的主考官 (Tech_Expert)。
你的核心任务是彻底考察候选人的技术深度和广度。

【工作准则与提问策略】
1. **结构化考察**：面试必须包含「项目深挖」与「核心八股文（基础底层知识）」两个部分。
2. **项目深挖**：针对候选人简历中提到的技术栈和项目，连续追问 3-5 轮细节。
   - 优先使用 `query_graph_rag` 查询候选人简历中的项目上下文。
   - 深入追问：为什么这么设计？遇到了什么难点？有哪些可以优化的地方？不要轻易放过候选人的回答，试着找出漏洞进行挑战。
3. **硬核八股文**：项目深挖后，转入基础底层知识考察。
   - 必须使用 `search_question_bank` 查询与候选人技术栈相关的面试题。
   - 根据查到的标答和追问点（Followups）层层递进，直至探测到候选人的知识盲区。
4. **控制话语**：这是语音口语交流。每次只问一个极其明确的问题（绝对不要一次连问三个问题），保持简练自然、压迫感适中，切忌长篇大论。
"""),
        ("placeholder", "{messages}")
    ])

    chain = prompt | llm_with_tools
    response = await chain.ainvoke({"messages": state["messages"]})

    # 将面试官的问题或工具调用记录追加入 state
    return {"messages": [response]}


async def hr_expert_node(state: InterviewState) -> dict:
    """
    行为考官 (Actor)。考察软技能。不使用工具。
    """
    llm = get_deepseek_llm("deepseek-chat")
    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是这场硅谷级别面试的资深 HRBP 考官 (HR_Expert)。
你的任务是进行 Behavioral 面试（行为面试），评估候选人的软技能和文化契合度。

【工作准则与提问策略】
1. **基于 STAR 原则**：深度挖掘候选人在团队协作、抗压能力、冲突解决、项目管理等方面的真实表现。
2. **打破砂锅问到底**：当候选人给出笼统表面的回答时，追问细节（例如：“当时具体是谁提出的反对意见？”“你采取的最关键的一步是什么？”）。
3. **职业规划与反思**：考察候选人的自我驱动力与失败复盘能力。
4. **控制话语**：每次只问一个简明扼要的问题，采用口语化的真实沟通方式，体现出 HRBP 的敏锐和专业。
"""),
        ("placeholder", "{messages}")
    ])

    chain = prompt | llm
    response = await chain.ainvoke({"messages": state["messages"]})
    return {"messages": [response]}


class EvaluationResult(BaseModel):
    feedback: str = Field(description="给出的简短文字点评，内部用")
    score_delta: int = Field(description="打分变化，-1(差), 0(一般), 1(好)")
    skill_category: str = Field(description="当前考察的技能分类，如 'React', 'System Design', 'Communication'")

async def evaluator_node(state: InterviewState) -> dict:
    """
    后台裁判 (Critic)。专门对最近一次用户的回答打分，更新能力矩阵。
    """
    llm = get_deepseek_llm("deepseek-chat")
    structured_llm = llm.with_structured_output(EvaluationResult, method="function_calling")

    # 取出最后一条用户消息和上一条 AI 问题
    if len(state["messages"]) >= 2:
        last_human_msg = state["messages"][-1]
        last_ai_msg = state["messages"][-2]
    else:
        return {} # 历史记录不足

    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一个专业且严厉的后台裁判 (Critic)。
你的唯一任务是对候选人刚刚回复的那句话进行评估，并量化更新候选人的能力矩阵。

【评估要求】
1. 分析候选人的回答是否准确、有深度、且逻辑清晰。
2. 如果回答含糊其辞、答非所问或有技术漏洞，果断给负分 (-1)。
3. 如果回答极其亮眼，有深度的系统思考，给出正分 (+1)。
4. 如果只是平庸地背诵标准答案，没有结合实际，给 0 分。
5. 提取本次问答考察的具体技能分类（例如：React, 微服务架构, 沟通协作能力）。
请严格输出 JSON 格式的结果。
"""),
        ("user", "面试官提问: {ai_msg}\n候选人回答: {human_msg}")
    ])

    result: EvaluationResult = await (prompt | structured_llm).ainvoke({
        "ai_msg": last_ai_msg.content,
        "human_msg": last_human_msg.content
    })

    # 拿到旧的 skill_matrix 并更新
    old_matrix = state.get("skill_matrix", {})
    new_matrix = dict(old_matrix)
    cat = result.skill_category
    new_matrix[cat] = new_matrix.get(cat, 0) + result.score_delta

    # 注意：裁判不发消息给用户，它只更新状态
    return {"skill_matrix": new_matrix}
