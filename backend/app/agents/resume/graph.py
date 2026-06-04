"""
LangGraph 简历优化工作流的状态机定义与长期记忆节点。
包含了 MCP 调用、自我审查循环 (Self-Correction) 以及记忆提取的完整图。
"""
import operator
import json
import os
from typing import Annotated, TypedDict, Any, Sequence, Optional

from langgraph.graph import StateGraph, END
from langchain_core.messages import AnyMessage, BaseMessage, SystemMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI

from app.agents.resume.mcp_server import list_tools, call_tool

# ---------------------------------------------------------
# 1. 状态定义 (State)
# ---------------------------------------------------------
class ResumeState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    resume_content: dict[str, Any]
    user_memory: dict | None
    user_id: Optional[int]
    resume_id: Optional[int]
    confirmation_queue: Any
    
    # 审查状态标志
    is_valid: bool
    feedback: str | None


# ---------------------------------------------------------
# 2. 简历编辑节点 (Editor Node) - 使用最强模型 (deepseek-v4-pro)
# ---------------------------------------------------------
async def editor_node(state: ResumeState) -> dict[str, Any]:
    """负责根据用户要求修改简历，并在需要时通过 MCP 工具执行。"""
    import os
    
    # 切换为默认的 gpt-4o，因为某些第三方 DeepSeek 代理无法正确解析 OpenAI 格式的 tool_calls
    model_name = os.environ.get("OPENAI_MODEL", "deepseek-v4-pro")
    llm = ChatOpenAI(model=model_name, temperature=0.3, streaming=True)
    
    mcp_tools = await list_tools()
    llm_with_tools = llm.bind_tools([
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.inputSchema
            }
        } for t in mcp_tools
    ])
    
    # 工业级强提示词 (Editor)
    sys_msg = SystemMessage(content=f"""
你是一位拥有10年经验的硅谷顶级 Tech Recruiter 及简历优化专家。
你的任务是严格遵循用户的要求，回答用户问题或者修改简历。

【当前简历数据结构】：
{json.dumps(state.get("resume_content", dict()), ensure_ascii=False)}

【行为准则】：
1. 如果用户是询问建议、咨询问题或闲聊，正常回答即可，不需要强制调用工具修改简历。
2. 如果用户明确要求修改简历，你必须使用 MCP 工具直接修改简历数据（切勿只在口头回复）。
3. 在调用工具修改简历之前，请务必用文本详细向用户说明：你把哪句话改成了什么样，以及为什么要这么改（例如补充了哪些量化指标）。然后再输出工具调用语句！

【简历优化原则（仅在修改简历时适用）】：
1. **Situation/Task**：明确业务背景与难点。
2. **Action**：以强动作动词开头。
3. **Result**：包含业务价值和量化指标。

【用户的长期偏好与约束】：
{json.dumps(state.get("user_memory") or {}, ensure_ascii=False)}

【自我纠错审查意见】：
{state.get("feedback", "无")}

请一步一步思考。如果需要调用工具，请准确传递参数。
""")
    
    messages = [sys_msg] + state.get("messages", [])
    response = await llm_with_tools.ainvoke(messages)
    
    tool_calls_to_execute = list(response.tool_calls)
    
    # 兼容处理：某些 DeepSeek 第三方 API 会漏解 tool_calls 并把 <｜｜DSML｜｜> 标签混入文本
    if not tool_calls_to_execute and isinstance(response.content, str) and "<｜｜DSML｜｜invoke" in response.content:
        import re, uuid
        invoke_pattern = r'<｜｜DSML｜｜invoke name="([^"]+)">([\s\S]*?)</｜｜DSML｜｜invoke>'
        param_pattern = r'<｜｜DSML｜｜parameter name="([^"]+)"[^>]*>([\s\S]*?)</｜｜DSML｜｜parameter>'
        for match in re.finditer(invoke_pattern, response.content):
            tool_name = match.group(1)
            params_str = match.group(2)
            args = {}
            for p_match in re.finditer(param_pattern, params_str):
                param_name = p_match.group(1)
                val_clean = p_match.group(2).strip()
                if val_clean.isdigit():
                    args[param_name] = int(val_clean)
                elif val_clean.lower() in ["true", "false"]:
                    args[param_name] = val_clean.lower() == "true"
                else:
                    args[param_name] = val_clean
            tc = {
                "name": tool_name,
                "args": args,
                "id": f"call_{uuid.uuid4().hex[:8]}"
            }
            tool_calls_to_execute.append(tc)
            if not hasattr(response, "tool_calls") or response.tool_calls is None:
                response.tool_calls = []
            response.tool_calls.append(tc)
        
        # 把原始 content 里的 DSML 代码剥离，避免前端直接展示或者影响后续逻辑
        response.content = re.sub(r'<｜｜DSML｜｜tool_calls>[\s\S]*?</｜｜DSML｜｜tool_calls>', '', response.content).strip()
            
    new_messages = [response]
    
    if tool_calls_to_execute:
        from langchain_core.callbacks.manager import dispatch_custom_event
        confirmation_queue = state.get("confirmation_queue")
        for tc in tool_calls_to_execute:
            args = tc["args"]
            args["_resume_content"] = state.get("resume_content", {})
            if state.get("user_id"): args["_user_id"] = state.get("user_id")
            if state.get("resume_id"): args["_resume_id"] = state.get("resume_id")
            
            # 分发 pending 事件，通知前端弹出确认卡片
            dispatch_custom_event("manual_tool_pending", {
                "name": tc["name"],
                "run_id": tc["id"],
                "args": args
            })
            
            # 阻塞等待用户确认
            if confirmation_queue is not None:
                confirmation = await confirmation_queue.get()
                if not confirmation:
                    dispatch_custom_event("manual_tool_rejected", {
                        "name": tc["name"],
                        "run_id": tc["id"]
                    })
                    new_messages.append(ToolMessage(
                        tool_call_id=tc["id"],
                        name=tc["name"],
                        content="User rejected the tool call."
                    ))
                    continue
                else:
                    dispatch_custom_event("manual_tool_confirmed", {
                        "name": tc["name"],
                        "run_id": tc["id"]
                    })
            
            mcp_result = await call_tool(tc["name"], args)
            tool_res_str = mcp_result[0].text if mcp_result else "Error: Empty tool response"
            dispatch_custom_event("manual_tool_end", {"name": tc["name"], "run_id": tc["id"], "output": tool_res_str})
            
            new_messages.append(ToolMessage(
                tool_call_id=tc["id"],
                name=tc["name"],
                content=tool_res_str
            ))
            
    return {"messages": new_messages}

# ---------------------------------------------------------
# 3. 自我审查节点 (Reviewer Node) - 使用快速小模型 (deepseek-v4-flash)
# ---------------------------------------------------------
async def reviewer_node(state: ResumeState) -> dict[str, Any]:
    """Actor-Critic 架构中的 Critic：执行严格的验收清单打分。"""
    messages = state.get("messages", [])
    
    # 切换为标准的审查小模型
    model_name = os.environ.get("OPENAI_MODEL_REVIEWER", "deepseek-v4-flash")
    llm = ChatOpenAI(model=model_name, temperature=0.0)
    
    # 调整后的打分清单，支持正常对话
    prompt = """
你是一位冷酷无情、极其严苛的简历验收审查官 (QA)。你的职责是挑错。
请审视前一位简历专家在最近一轮中生成的文本及执行的工具结果。

【验收强制 Checklist】：
1. **是否调用了工具**：如果用户的请求是询问建议、提问或闲聊（不需要修改简历），那么不调用工具也是完全可以的，判定为合格。如果用户要求了修改，且专家口头答应修改但没调用修改工具，则判定为不合格。
2. **错误监控**：如果调用了工具，其返回值是否包含不可恢复的错误？如果有，要求修复。
3. **内容质量**：如果调用了修改工具，修改后的内容是否增加了量化指标？动词是否足够强？如果没有，给出建议。

如果不满足以上条件，请明确指出失败的具体规则编号，并给出具体的修改建议。如果合格，则直接通过。
"""
    
    from pydantic import BaseModel, Field
    
    class ValidationResult(BaseModel):
        is_valid: bool = Field(description="是否通过审查（纯聊天不调用工具也算通过）")
        feedback: str | None = Field(default=None, description="如果不通过，给出修改指令。通过则为空。")

    eval_llm = llm.with_structured_output(ValidationResult)
    
    try:
        result = await eval_llm.ainvoke([SystemMessage(content=prompt)] + messages[-3:])
        return {
            "is_valid": result.is_valid,
            "feedback": result.feedback if not result.is_valid else None
        }
    except Exception as e:
        print(f"Reviewer Node Error: {e}")
        return {"is_valid": True, "feedback": None}

# ---------------------------------------------------------
# 4. 长期记忆提取节点 (异步调用)
# ---------------------------------------------------------
async def extract_memory_async(messages: list[AnyMessage], current_preferences: dict | None) -> dict | None:
    """对话结束时异步提取用户偏好，输出 JSON 格式以便保存到数据库。"""
    
    human_messages = [msg for msg in messages if isinstance(msg, HumanMessage) or (isinstance(msg, dict) and msg.get("type") == "human")]
    if not human_messages:
        return None

    model_name = os.environ.get("OPENAI_MODEL_MEMORY", "deepseek-v4-flash")
    llm = ChatOpenAI(model=model_name, temperature=0.1)
    
    system_prompt = f"""
你是用户偏好记忆分析引擎。请精读以下对话，挖掘出用户在职业规划和简历编写上的【底层逻辑与偏好约束】。

当前已有记忆档案：\n{json.dumps(current_preferences or {}, ensure_ascii=False)}\n

要求：
1. 识别并补充新的约束条件（例如：“不要提Python，主攻Java”、“字数要求极简”、“要求量化指标”等）。
2. 去除冲突或过时的偏好。
3. 返回的结果必须是一个完整的 JSON 对象，包含用户偏好的各个维度（例如：技术栈偏好、排版风格、语言风格、业务侧重点等）。
"""
    
    from pydantic import BaseModel, Field
    
    class UserPreferences(BaseModel):
        technical_skills: list[str] = Field(default_factory=list, description="用户偏好的技术栈或不想提的技术")
        formatting_style: str = Field(default="", description="排版风格要求，如极简、详细等")
        language_style: str = Field(default="", description="语言风格，如强动词、量化指标等")
        focus_areas: list[str] = Field(default_factory=list, description="业务侧重点，如后端架构、前端性能等")
        other_constraints: list[str] = Field(default_factory=list, description="其他的偏好或约束")

    extraction_messages = [SystemMessage(content=system_prompt)] + messages[-5:]
    eval_llm = llm.with_structured_output(UserPreferences)
    try:
        response = await eval_llm.ainvoke(extraction_messages)
        return response.model_dump()
    except Exception as e:
        print(f"Memory Extractor Error: {e}")
        return None

# ---------------------------------------------------------
# 5. 路由逻辑与拓扑编译 (Routing & Compilation)
# ---------------------------------------------------------
def should_continue(state: ResumeState) -> str:
    """决定是打回重做，还是顺利结束。"""
    if state.get("is_valid"):
        return END
    else:
        return "editor"

def route_after_editor(state: ResumeState) -> str:
    messages = state.get("messages", [])
    if len(messages) >= 2 and isinstance(messages[-2], ToolMessage):
        return "reviewer"
    return END

def build_graph():
    """编译图结构"""
    workflow = StateGraph(ResumeState)
    
    workflow.add_node("editor", editor_node)
    workflow.add_node("reviewer", reviewer_node)
    
    workflow.set_entry_point("editor")
    
    workflow.add_conditional_edges(
        "editor",
        route_after_editor,
        {
            "reviewer": "reviewer",
            END: END
        }
    )
    
    workflow.add_conditional_edges(
        "reviewer",
        should_continue,
        {
            "editor": "editor",              # 如果不合格，连线回 Editor 重做
            END: END                           # 如果合格，直接结束
        }
    )
    
    return workflow.compile()

__all__ = ["ResumeState", "extract_memory_async", "build_graph"]
