import os
from langchain_openai import ChatOpenAI
from app.services.llm.compatible_llm import completion_options

def get_deepseek_llm(model_name: str = "deepseek-chat") -> ChatOpenAI:
    """
    获取 DeepSeek 模型实例。
    """
    return ChatOpenAI(
        api_key=os.environ.get("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
        model=os.environ.get("DEEPSEEK_MODEL") or model_name,
        extra_body=completion_options("https://api.deepseek.com"),
        # 默认禁用流式，LangGraph 的 stream_events 会处理流式逻辑
        streaming=False,
    )
