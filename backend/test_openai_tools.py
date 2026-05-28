import asyncio
import json
from app.agents.resume.agent import ResumeAgent
from app.runtime.pi_agent_openrouter import _openai_tools
from pi_agent_core import AgentContext

async def main():
    agent = ResumeAgent()
    
    # We need to build the context
    context_dict = {
        "tool_profile": "resume_edit",
        "confirmed_diff_items": []
    }
    from app.runtime.pi_agent_runtime import PiAgentRuntime
    runtime = PiAgentRuntime()
    tools_schema = runtime._profiled_tool_schemas(agent.definition, "resume_edit")
    tools = runtime._build_tools(
        agent=agent.definition,
        tools_schema=tools_schema,
        context=context_dict,
        confirmation_queue=None,
        event_queue=None,
        event_callback=None,
        run_id="test",
        executed_tools=[],
        stream_state={}
    )
    
    ctx = AgentContext(system_prompt="", messages=[], tools=tools)
    openai_tools = _openai_tools(ctx)
    with open("test_tools.json", "w", encoding="utf-8") as f:
        json.dump(openai_tools, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    asyncio.run(main())
