import asyncio
from langchain_core.messages import HumanMessage
from app.agents.interview.graph import interview_agent

async def main():
    config = {"configurable": {"thread_id": "test_1"}}
    input_state = {"messages": [HumanMessage(content="你好，我是张三，来面试前端。")]}
    full = ""

    print("Starting stream...")
    async for msg, metadata in interview_agent.astream(input_state, config=config, stream_mode="messages"):
        node = metadata.get("langgraph_node")
        if node in ("Tech_Expert", "HR_Expert"):
            if msg.content:
                print(msg.content, end="", flush=True)
                full += msg.content
    print("\n--- Done ---")
    print("Full:", full)

if __name__ == "__main__":
    asyncio.run(main())
