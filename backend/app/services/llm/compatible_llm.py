"""Compatibility for the official DeepSeek Chat Completions endpoint."""
import os
from urllib.parse import urlparse

from langchain_openai import ChatOpenAI


def completion_options(api_base: str) -> dict:
    # Existing agent history does not retain reasoning_content for tool turns.
    # Use the documented non-thinking mode so tool-result round trips stay valid.
    if urlparse(api_base).hostname == 'api.deepseek.com':
        return {'thinking': {'type': 'disabled'}}
    return {}


def resume_chat_model(model: str, **kwargs) -> ChatOpenAI:
    base = os.getenv('OPENAI_API_BASE') or os.getenv('OPENAI_BASE_URL') or ''
    return ChatOpenAI(model=model, extra_body=completion_options(base), **kwargs)
