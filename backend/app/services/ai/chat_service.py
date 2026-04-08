"""
AI 聊天服务模块

提供基于 OpenRouter 的统一 AI 聊天接口。
"""

import asyncio
import logging
from time import perf_counter
from typing import Dict, Any, List, Optional, AsyncGenerator, overload, Literal

import httpx

from app.core.config import settings


logger = logging.getLogger(__name__)


class ChatService:
    """AI 聊天服务类，基于 OpenRouter"""

    def __init__(self):
        """初始化聊天服务"""
        self.api_key = settings.OPENROUTER_API_KEY
        self.api_base = settings.OPENROUTER_API_BASE
        self.model = settings.OPENROUTER_MODEL
        self.timeout = httpx.Timeout(
            connect=settings.OPENROUTER_CONNECT_TIMEOUT_SECONDS,
            read=settings.OPENROUTER_READ_TIMEOUT_SECONDS,
            write=settings.OPENROUTER_WRITE_TIMEOUT_SECONDS,
            pool=settings.OPENROUTER_READ_TIMEOUT_SECONDS,
        )
        self.max_retries = max(0, settings.OPENROUTER_MAX_RETRIES)
        self.retry_backoff_seconds = max(
            0.0, settings.OPENROUTER_RETRY_BACKOFF_SECONDS
        )
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://chat-resume.com",
            "X-Title": "Chat Resume AI Assistant",
        }
        self.client = httpx.AsyncClient(timeout=self.timeout)

    async def __aenter__(self):
        """上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        await self.close()

    async def close(self):
        """关闭 HTTP 客户端"""
        await self.client.aclose()

    @overload
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: Literal[False] = False,
        tools: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]: ...

    @overload
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: Literal[True] = True,
        tools: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
    ) -> AsyncGenerator[str, None]: ...

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        tools: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
    ):
        """统一的聊天完成接口

        Args:
            messages: 聊天消息列表
            temperature: 生成温度
            max_tokens: 最大token数
            stream: 是否流式返回
            tools: 工具定义列表（Function Calling）
            system_prompt: 系统提示词

        Returns:
            AI响应结果(流式时为异步生成器,非流式时为字典)
        """
        if not self.api_key:
            raise ValueError("未配置 OpenRouter API 密钥")

        # 添加系统提示
        if system_prompt:
            if not messages or messages[0].get("role") != "system":
                messages = [{"role": "system", "content": system_prompt}] + messages

        if stream:
            return self._chat_completion_stream(messages, temperature, max_tokens)
        else:
            return await self._chat_completion_non_stream(
                messages, temperature, max_tokens, tools
            )

    async def _chat_completion_non_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """非流式聊天完成"""
        payload = self._build_payload(
            messages, temperature, max_tokens, stream=False, tools=tools
        )
        url = self._get_endpoint_url()
        started_at = perf_counter()
        response = await self._post_with_retries(url, payload)
        elapsed = perf_counter() - started_at
        logger.info(
            "OpenRouter non-stream completed model=%s elapsed=%.2fs tools=%s",
            self.model,
            elapsed,
            bool(tools),
        )
        return response.json()

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
            async for chunk in self._handle_stream_response(url, payload):
                yield chunk
        except httpx.HTTPStatusError as e:
            raise Exception(
                f"AI服务请求失败: {e.response.status_code} - {e.response.text}"
            )
        except Exception as e:
            raise Exception(f"AI服务请求异常: {str(e)}")

    async def chat_completion_stream_deltas(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """流式聊天，产出解析后的 delta 对象（同时支持 content 和 tool_calls）"""
        import json as _json

        if system_prompt:
            if not messages or messages[0].get("role") != "system":
                messages = [{"role": "system", "content": system_prompt}] + messages

        payload = self._build_payload(messages, temperature, max_tokens, stream=True, tools=tools)
        url = self._get_endpoint_url()

        try:
            async with self.client.stream(
                "POST", url, json=payload, headers=self.headers, timeout=self.timeout
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = _json.loads(data)
                        delta = chunk["choices"][0].get("delta", {})
                        yield delta
                    except (KeyError, IndexError, _json.JSONDecodeError):
                        continue
        except httpx.HTTPStatusError as e:
            raise Exception(f"AI服务请求失败: {e.response.status_code} - {e.response.text}")
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

        return payload

    def _get_endpoint_url(self) -> str:
        """获取 API 端点 URL"""
        return f"{self.api_base}/chat/completions"

    async def _handle_stream_response(
        self, url: str, payload: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """处理流式响应"""
        async with self.client.stream(
            "POST", url, json=payload, headers=self.headers, timeout=self.timeout
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    yield data

    async def _post_with_retries(
        self, url: str, payload: Dict[str, Any]
    ) -> httpx.Response:
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                logger.debug(
                    "OpenRouter request attempt=%s model=%s max_retries=%s",
                    attempt + 1,
                    self.model,
                    self.max_retries,
                )
                response = await self.client.post(
                    url,
                    json=payload,
                    headers=self.headers,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                body = e.response.text[:500]
                logger.warning(
                    "OpenRouter HTTP error attempt=%s status=%s body=%s",
                    attempt + 1,
                    status,
                    body,
                )
                # 4xx 通常是不可恢复错误，直接抛出
                if 400 <= status < 500 and status != 429:
                    raise Exception(f"AI服务请求失败: {status} - {body}") from e
                last_error = e
            except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as e:
                logger.warning(
                    "OpenRouter network error attempt=%s type=%s message=%s",
                    attempt + 1,
                    type(e).__name__,
                    str(e),
                )
                last_error = e
            except Exception as e:
                logger.exception("OpenRouter unexpected error attempt=%s", attempt + 1)
                last_error = e

            if attempt < self.max_retries:
                await asyncio.sleep(self.retry_backoff_seconds * (attempt + 1))

        if isinstance(last_error, httpx.HTTPStatusError):
            raise Exception(
                f"AI服务请求失败: {last_error.response.status_code} - {last_error.response.text[:500]}"
            ) from last_error
        raise Exception(f"AI服务请求异常: {str(last_error) if last_error else 'unknown error'}")

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
        import logging

        logger = logging.getLogger(__name__)

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

        # 调试日志：打印完整的消息列表
        logger.info("=== chat_with_context 完整消息列表 ===")
        logger.info(f"总共 {len(messages)} 条消息:")
        for i, msg in enumerate(messages):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            # 截取内容前100个字符用于日志
            content_preview = content[:100] + "..." if len(content) > 100 else content
            logger.info(f"  [{i}] {role}: {content_preview}")

        # 调用AI服务
        response = await self._chat_completion_non_stream(messages)

        # 提取回复内容
        return response.get("choices", [{}])[0].get("message", {}).get("content", "")
