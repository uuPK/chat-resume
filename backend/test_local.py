import asyncio
from app.agents.resume.graph import build_graph, ResumeState
from langchain_core.messages import HumanMessage
from app.infra.database import SessionLocal
from app.models.user import User
import sys
# Set encoding for Windows console if needed
sys.stdout.reconfigure(encoding='utf-8')

async def run_test():
    workflow = build_graph()
    
    # Fake state
    state = {
        "messages": [HumanMessage(content="帮我把我的工作经历修改得更加量化一点")],
        "resume_content": {
            "work_experience": [
                {
                    "company": "测试公司",
                    "position": "开发工程师",
                    "description": "做了很多需求，写了很多代码，修复了很多bug"
                }
            ]
        },
        "user_memory": {"language_style": "严谨专业"},
        "user_id": 1,
        "resume_id": 1,
        "confirmation_queue": asyncio.Queue(),
        "is_valid": False,
        "feedback": None
    }
    
    print('Starting graph execution...')
    async for event in workflow.astream_events(state, version='v2'):
        kind = event['event']
        if kind == 'on_custom_event' and event.get('name') == 'manual_tool_pending':
            print(f"\n[EVENT] Tool pending: {event['data']['name']}")
            print("[TEST] Auto-confirming tool call!")
            await state['confirmation_queue'].put(True)
        elif kind == 'on_chat_model_stream':
            chunk = event['data']['chunk'].content
            if chunk:
                print(chunk, end='', flush=True)
                
    print('\nExecution finished!')

if __name__ == '__main__':
    asyncio.run(run_test())
