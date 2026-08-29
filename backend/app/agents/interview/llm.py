import os
from langchain_openai import ChatOpenAI

def get_deepseek_llm(model_name: str = "deepseek-chat") -> ChatOpenAI:
    """
    获取 DeepSeek 模型实例。
    """
    return ChatOpenAI(
        api_key=os.environ.get("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
        model=model_name,
        # 默认禁用流式，LangGraph 的 stream_events 会处理流式逻辑
        streaming=False,
    )
