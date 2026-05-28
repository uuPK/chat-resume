import asyncio
import httpx
from app.infra.config import settings
from app.runtime.pi_agent_runtime import PiAgentRuntime
from app.agents.resume.agent import ResumeAgent
from pi_agent_core import AgentContext
from app.runtime import pi_agent_openrouter
import json

# Monkey patch _normalize_tool_schema for testing
def patched_normalize_tool_schema(schema):
    if isinstance(schema, list):
        return [patched_normalize_tool_schema(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    normalized = {}
    for key, value in schema.items():
        if key == "properties" and isinstance(value, dict):
            normalized[key] = {k: patched_normalize_tool_schema(v) for k, v in value.items()}
        else:
            normalized[key] = patched_normalize_tool_schema(value)
    if "type" not in normalized and (schema_type := pi_agent_openrouter._infer_schema_type(normalized)):
        normalized["type"] = schema_type
    return normalized

pi_agent_openrouter._normalize_tool_schema = patched_normalize_tool_schema

async def main():
    agent = ResumeAgent()
    runtime = PiAgentRuntime()
    
    context_dict = {
        "tool_profile": "resume_edit",
        "confirmed_diff_items": []
    }
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
    openai_tools = pi_agent_openrouter._openai_tools(ctx)
    
    api_key = settings.OPENROUTER_API_KEY
    api_base = settings.OPENROUTER_API_BASE
    
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": "hi"}],
        "tools": openai_tools,
    }
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{api_base}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"}
        )
        print("Status code:", resp.status_code)
        try:
            print("Response:", resp.text.encode('utf-8').decode('utf-8'))
        except Exception:
            print("Response (repr):", repr(resp.text))

if __name__ == "__main__":
    asyncio.run(main())
