"""
统一AI聊天服务模块

提供统一的AI聊天接口，整合多个AI模型提供商。
支持OpenRouter、DeepSeek、Gemini等服务，提供一致的API体验。
"""

import httpx
from typing import Dict, Any, List, Optional, AsyncGenerator
from enum import Enum
from app.core.config import settings


class AIProvider(str, Enum):
    """AI服务提供商枚举"""

    OPENROUTER = "openrouter"
    DEEPSEEK = "deepseek"
    GEMINI = "gemini"


class ChatService:
    """统一AI聊天服务类，支持多种AI模型"""

    def __init__(self, provider: AIProvider = AIProvider.OPENROUTER):
        """初始化聊天服务

        Args:
            provider: AI服务提供商，默认使用OpenRouter
        """
        self.provider = provider
        self._setup_provider()

    def _setup_provider(self):
        """根据选择的提供商配置连接参数"""
        if self.provider == AIProvider.OPENROUTER:
            self.api_key = settings.OPENROUTER_API_KEY
            self.api_base = settings.OPENROUTER_API_BASE
            self.model = settings.OPENROUTER_MODEL
            self.headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://chat-resume.com",
                "X-Title": "Chat Resume AI Assistant",
            }
        elif self.provider == AIProvider.DEEPSEEK:
            self.api_key = settings.DEEPSEEK_API_KEY
            self.api_base = settings.DEEPSEEK_API_BASE
            self.model = "deepseek-chat"
            self.headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
        elif self.provider == AIProvider.GEMINI:
            self.api_key = settings.GEMINI_API_KEY
            self.api_base = settings.GEMINI_API_BASE
            self.model = "gemini-pro"
            self.headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ):
        """统一的聊天完成接口

        Args:
            messages: 聊天消息列表
            temperature: 生成温度
            max_tokens: 最大token数
            stream: 是否流式返回

        Returns:
            AI响应结果(流式时为异步生成器,非流式时为字典)
        """
        if not self.api_key:
            raise ValueError(f"未配置 {self.provider.value} API密钥")

        if stream:
            return self._chat_completion_stream(messages, temperature, max_tokens)
        else:
            return await self._chat_completion_non_stream(
                messages, temperature, max_tokens
            )

    async def _chat_completion_non_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """非流式聊天完成"""
        payload = self._build_payload(messages, temperature, max_tokens, stream=False)
        url = self._get_endpoint_url()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=self.headers)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            raise Exception(
                f"AI服务请求失败: {e.response.status_code} - {e.response.text}"
            )
        except Exception as e:
            raise Exception(f"AI服务请求异常: {str(e)}")

    async def _chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """流式聊天完成"""
        payload = self._build_payload(messages, temperature, max_tokens, stream=True)
        url = self._get_endpoint_url()

        try:
            async with httpx.AsyncClient() as client:
                async for chunk in self._handle_stream_response(client, url, payload):
                    yield chunk
        except httpx.HTTPStatusError as e:
            raise Exception(
                f"AI服务请求失败: {e.response.status_code} - {e.response.text}"
            )
        except Exception as e:
            raise Exception(f"AI服务请求异常: {str(e)}")

    def _build_payload(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: Optional[int],
        stream: bool,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """构建请求载荷"""
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens

        # 添加工具定义（Function Calling）
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        # 针对不同提供商的特殊处理
        if self.provider == AIProvider.DEEPSEEK and not max_tokens:
            payload["max_tokens"] = 2000

        return payload

    def _get_endpoint_url(self) -> str:
        """获取API端点URL"""
        if self.provider == AIProvider.OPENROUTER:
            return f"{self.api_base}/chat/completions"
        elif self.provider == AIProvider.DEEPSEEK:
            return f"{self.api_base}/chat/completions"
        elif self.provider == AIProvider.GEMINI:
            return f"{self.api_base}/v1beta/models/{self.model}:generateContent"

        raise ValueError(f"不支持的AI提供商: {self.provider}")

    async def _handle_stream_response(
        self, client: httpx.AsyncClient, url: str, payload: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """处理流式响应"""
        async with client.stream(
            "POST", url, json=payload, headers=self.headers
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    yield data

    async def chat_with_context(
        self,
        message: str,
        context: Optional[str] = None,
        system_prompt: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """带上下文的聊天对话

        Args:
            message: 用户消息
            context: 上下文信息
            system_prompt: 系统提示词
            conversation_history: 对话历史

        Returns:
            AI回复内容
        """
        messages = []

        # 添加系统提示
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # 添加上下文
        if context:
            messages.append({"role": "system", "content": f"上下文信息：\n{context}"})

        # 添加对话历史
        if conversation_history:
            messages.extend(conversation_history[-10:])  # 保留最近10轮对话

        # 添加当前消息
        messages.append({"role": "user", "content": message})

        # 调用AI服务
        response = await self._chat_completion_non_stream(messages)

        # 提取回复内容
        if self.provider == AIProvider.GEMINI:
            return (
                response.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )
        else:
            return (
                response.get("choices", [{}])[0].get("message", {}).get("content", "")
            )

    async def chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """支持工具调用的聊天接口

        Args:
            messages: 消息列表
            system_prompt: 系统提示词
            tools: 工具定义列表
            temperature: 生成温度
            max_tokens: 最大token数

        Returns:
            完整的AI响应（包含工具调用信息）
        """
        # 添加系统提示
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + messages

        # 构建载荷
        payload = self._build_payload(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
            tools=tools
        )

        url = self._get_endpoint_url()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=self.headers)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            raise Exception(
                f"AI服务请求失败: {e.response.status_code} - {e.response.text}"
            )
        except Exception as e:
            raise Exception(f"AI服务请求异常: {str(e)}")

    def switch_provider(self, provider: AIProvider):
        """切换AI服务提供商

        Args:
            provider: 新的AI服务提供商
        """
        self.provider = provider
        self._setup_provider()
