"""用于把 OpenRouter 流式响应适配为 pi-agent-core 事件。"""

from __future__ import annotations

import asyncio
import json
import logging
import random
from dataclasses import dataclass
from time import monotonic
from typing import Any

import httpx
from pi_agent_core import (
    AgentContext,
    AssistantMessage,
    AssistantMessageEvent,
    Model,
    SimpleStreamOptions,
    StreamDoneEvent,
    StreamErrorEvent,
    StreamResult,
    StreamStartEvent,
    StreamTextDeltaEvent,
    StreamTextEndEvent,
    StreamTextStartEvent,
    StreamToolCallEndEvent,
    StreamToolCallStartEvent,
    TextContent,
    ToolCall,
    StopReason,
    Usage,
)

from app.infra.config import settings


async def stream_openrouter(
    model: Model,
    context: AgentContext,
    options: SimpleStreamOptions,
) -> StreamResult:
    """用于处理流式OpenRouter。"""
    queue: asyncio.Queue[AssistantMessageEvent | None] = asyncio.Queue()
    done = asyncio.Event()
    state: dict[str, AssistantMessage | None] = {"final": None}
    partial = AssistantMessage(api=model.api, provider=model.provider, model=model.id)

    async def events_iter():
        """用于按顺序输出适配后的流式事件。"""
        while True:
            event = await queue.get()
            if event is None:
                return
            yield event

    async def result() -> AssistantMessage:
        """用于等待并返回最终助手消息。"""
        await done.wait()
        final = state["final"]
        if final is None:
            raise RuntimeError("OpenRouter stream ended without a final message")
        return final

    async def run_stream() -> None:
        """用于拉取模型流并写入本地事件队列。"""
        try:
            await _pump_with_retry(model, context, options, partial, queue)
            state["final"] = partial
        except Exception as exc:
            partial.stop_reason = "error"
            partial.error_message = str(exc)
            queue.put_nowait(StreamErrorEvent(reason="error", error=partial))
            state["final"] = partial
        finally:
            done.set()
            queue.put_nowait(None)

    asyncio.create_task(run_stream())
    return {"events": events_iter(), "result": result}


_logger = logging.getLogger(__name__)

# 需要重试的 HTTP 状态码
_RETRY_STATUS_CODES = {429, 502, 503, 504}
_RETRY_BASE_SECONDS = 1.0
_RETRY_MAX_WAIT_SECONDS = 30.0


class OpenRouterHTTPError(Exception):
    """携带 HTTP 状态码和可选 Retry-After 的 OpenRouter 错误。"""

    def __init__(self, status_code: int, message: str, retry_after: float | None = None) -> None:
        """初始化并保存状态码和 Retry-After 值。"""
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after


class OpenRouterCircuitOpenError(Exception):
    """表示 OpenRouter circuit breaker 已打开，当前请求被快速拒绝。"""


@dataclass
class _OpenRouterCircuitBreaker:
    """用于记录 OpenRouter 调用失败状态并决定是否快速失败。"""

    failure_count: int = 0
    opened_at: float | None = None

    def before_request(self, *, enabled: bool, cooldown_seconds: float) -> None:
        """请求前检查 circuit 是否仍处于 open 冷却期。"""
        if not enabled or self.opened_at is None:
            return
        if monotonic() - self.opened_at >= cooldown_seconds:
            self.opened_at = None
            return
        raise OpenRouterCircuitOpenError("OpenRouter circuit breaker is open")

    def record_success(self) -> None:
        """请求成功后清空失败状态。"""
        self.failure_count = 0
        self.opened_at = None

    def record_failure(self, *, enabled: bool, threshold: int) -> None:
        """请求最终失败后累加失败次数并在达到阈值时打开 circuit。"""
        if not enabled:
            return
        self.failure_count += 1
        if self.failure_count >= threshold:
            self.opened_at = monotonic()


_OPENROUTER_CIRCUIT_BREAKER = _OpenRouterCircuitBreaker()


def _reset_openrouter_circuit_breaker() -> None:
    """用于测试或进程内恢复时重置 OpenRouter circuit breaker。"""
    _OPENROUTER_CIRCUIT_BREAKER.record_success()


def _retry_wait(attempt: int, retry_after: float | None) -> float:
    """根据重试次数计算指数退避等待时间，优先使用 Retry-After 头的值。"""
    if retry_after is not None:
        return min(retry_after, _RETRY_MAX_WAIT_SECONDS)
    backoff = _RETRY_BASE_SECONDS * (2 ** attempt) + random.uniform(0, 1)
    return min(backoff, _RETRY_MAX_WAIT_SECONDS)


def _is_retryable_status(status_code: int) -> bool:
    """判断 HTTP 状态码是否应该触发重试。"""
    return status_code in _RETRY_STATUS_CODES


async def _pump_with_retry(
    model: Model,
    context: AgentContext,
    options: SimpleStreamOptions,
    partial: AssistantMessage,
    queue: asyncio.Queue[AssistantMessageEvent | None],
) -> None:
    """包装 _pump_openrouter_stream，对可重试错误执行指数退避重试。"""
    max_retries = settings.OPENROUTER_MAX_RETRIES
    circuit_enabled = settings.OPENROUTER_CIRCUIT_BREAKER_ENABLED
    circuit_failure_threshold = settings.OPENROUTER_CIRCUIT_BREAKER_FAILURE_THRESHOLD
    circuit_cooldown_seconds = settings.OPENROUTER_CIRCUIT_BREAKER_COOLDOWN_SECONDS
    last_exc: Exception | None = None

    _OPENROUTER_CIRCUIT_BREAKER.before_request(
        enabled=circuit_enabled,
        cooldown_seconds=circuit_cooldown_seconds,
    )

    for attempt in range(max_retries + 1):
        try:
            await _pump_openrouter_stream(model, context, options, partial, queue)
            _OPENROUTER_CIRCUIT_BREAKER.record_success()
            return
        except OpenRouterHTTPError as exc:
            if not _is_retryable_status(exc.status_code):
                raise
            last_exc = exc
            retry_after = exc.retry_after
            status_code: int | None = exc.status_code
        except (httpx.ConnectError, httpx.ReadTimeout) as exc:
            last_exc = exc
            retry_after = None
            status_code = None

        if attempt >= max_retries:
            break

        wait = _retry_wait(attempt, retry_after)
        _logger.warning(
            "OpenRouter 请求失败，准备重试 attempt=%d/%d status=%s wait=%.1fs error=%s",
            attempt + 1,
            max_retries,
            status_code,
            wait,
            last_exc,
        )
        await asyncio.sleep(wait)

    assert last_exc is not None
    _OPENROUTER_CIRCUIT_BREAKER.record_failure(
        enabled=circuit_enabled,
        threshold=circuit_failure_threshold,
    )
    raise last_exc


async def _pump_openrouter_stream(
    model: Model,
    context: AgentContext,
    options: SimpleStreamOptions,
    partial: AssistantMessage,
    queue: asyncio.Queue[AssistantMessageEvent | None],
) -> None:
    """用于处理pumpOpenRouter流式。"""
    body = _openrouter_body(model, context, options)
    headers = _openrouter_headers(options)
    text_started = False
    text_index = 0
    text_buffer: list[str] = []
    tool_buffers: dict[int, dict[str, Any]] = {}
    finish_reason = "stop"

    timeout = httpx.Timeout(
        connect=settings.OPENROUTER_CONNECT_TIMEOUT_SECONDS,
        read=settings.OPENROUTER_READ_TIMEOUT_SECONDS,
        write=settings.OPENROUTER_WRITE_TIMEOUT_SECONDS,
        pool=settings.OPENROUTER_CONNECT_TIMEOUT_SECONDS,
    )
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream(
            "POST",
            f"{settings.OPENROUTER_API_BASE.rstrip('/')}/chat/completions",
            headers=headers,
            json=body,
        ) as response:
            await _raise_for_openrouter_error(response)
            queue.put_nowait(StreamStartEvent(partial=partial))
            async for line in response.aiter_lines():
                if _cancelled(options):
                    raise RuntimeError("Request aborted by user")
                chunk = _decode_sse_line(line)
                if chunk is None:
                    continue
                if chunk == "[DONE]":
                    break
                if not isinstance(chunk, dict):
                    continue
                text_started = _apply_openrouter_chunk(
                    chunk=chunk,
                    partial=partial,
                    queue=queue,
                    tool_buffers=tool_buffers,
                    text_buffer=text_buffer,
                    text_started=text_started,
                    text_index=text_index,
                )
                finish_reason = _finish_reason(chunk, finish_reason)

    if text_started:
        queue.put_nowait(
            StreamTextEndEvent(
                content_index=text_index,
                content="".join(text_buffer),
                partial=partial,
            )
        )
    _emit_tool_calls(tool_buffers, partial, queue)
    partial.stop_reason = "toolUse" if tool_buffers else _stop_reason(finish_reason)
    queue.put_nowait(StreamDoneEvent(reason=partial.stop_reason, message=partial))


def _openrouter_body(
    model: Model,
    context: AgentContext,
    options: SimpleStreamOptions,
) -> dict[str, Any]:
    """用于处理OpenRouter请求体。"""
    body: dict[str, Any] = {
        "model": model.id,
        "messages": _openai_messages(context),
        "tools": _openai_tools(context),
        "stream": True,
        "stream_options": {"include_usage": True},
        "parallel_tool_calls": False,
    }
    if options.temperature is not None:
        body["temperature"] = options.temperature
    if options.max_tokens is not None:
        body["max_tokens"] = options.max_tokens
    return body


def _openrouter_headers(options: SimpleStreamOptions) -> dict[str, str]:
    """用于处理OpenRouter请求头。"""
    api_key = options.api_key or settings.OPENROUTER_API_KEY
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://chat-resume.com",
        "X-Title": "Chat Resume AI Assistant",
    }


def _openai_messages(context: AgentContext) -> list[dict[str, Any]]:
    """用于处理OpenAI 兼容消息列表。"""
    messages: list[dict[str, Any]] = []
    if context.system_prompt:
        messages.append({"role": "system", "content": context.system_prompt})
    for message in context.messages:
        converted = _openai_message(message)
        if converted is not None:
            messages.append(converted)
    return messages


def _openai_message(message: Any) -> dict[str, Any] | None:
    """用于处理OpenAI 兼容消息。"""
    role = getattr(message, "role", "")
    if role == "user":
        return {"role": "user", "content": _text_content(message)}
    if role == "assistant":
        return _openai_assistant_message(message)
    if role == "toolResult":
        return {
            "role": "tool",
            "tool_call_id": message.tool_call_id,
            "name": message.tool_name,
            "content": _text_content(message),
        }
    return None


def _openai_assistant_message(message: Any) -> dict[str, Any]:
    """用于处理OpenAI 兼容助手消息。"""
    tool_calls = []
    for block in getattr(message, "content", []):
        if isinstance(block, ToolCall):
            tool_calls.append(
                {
                    "id": block.id,
                    "type": "function",
                    "function": {
                        "name": block.name,
                        "arguments": json.dumps(
                            block.arguments,
                            ensure_ascii=False,
                        ),
                    },
                }
            )
    content = _text_content(message)
    payload: dict[str, Any] = {"role": "assistant", "content": content or None}
    if tool_calls:
        payload["tool_calls"] = tool_calls
    return payload


def _text_content(message: Any) -> str:
    """用于处理文本content。"""
    parts: list[str] = []
    for block in getattr(message, "content", []):
        if isinstance(block, TextContent):
            parts.append(block.text)
    return "".join(parts)


def _openai_tools(context: AgentContext) -> list[dict[str, Any]]:
    """用于处理OpenAI 兼容工具列表。"""
    tools = []
    for tool in context.tools:
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters.model_dump(),
                },
            }
        )
    return tools


async def _raise_for_openrouter_error(response: httpx.Response) -> None:
    """读取错误响应体并抛出携带状态码和 Retry-After 的 OpenRouterHTTPError。"""
    if response.status_code == 200:
        return
    retry_after_header = response.headers.get("Retry-After")
    retry_after: float | None = None
    if retry_after_header is not None:
        try:
            retry_after = float(retry_after_header)
        except ValueError:
            pass
    body = await response.aread()
    message = body.decode("utf-8", errors="replace")
    raise OpenRouterHTTPError(
        status_code=response.status_code,
        message=f"OpenRouter error {response.status_code}: {message}",
        retry_after=retry_after,
    )


def _decode_sse_line(line: str) -> dict[str, Any] | str | None:
    """用于处理decodesseline。"""
    if not line.startswith("data: "):
        return None
    data = line[6:].strip()
    if not data:
        return None
    if data == "[DONE]":
        return data
    return json.loads(data)


def _apply_openrouter_chunk(
    *,
    chunk: dict[str, Any],
    partial: AssistantMessage,
    queue: asyncio.Queue[AssistantMessageEvent | None],
    tool_buffers: dict[int, dict[str, Any]],
    text_buffer: list[str],
    text_started: bool,
    text_index: int,
) -> bool:
    """用于应用OpenRouterchunk。"""
    choice = _first_choice(chunk)
    if not choice:
        _apply_usage(chunk, partial)
        return text_started
    delta = choice.get("delta") or {}
    text_started = _apply_text_delta(
        delta=delta,
        partial=partial,
        queue=queue,
        text_buffer=text_buffer,
        text_started=text_started,
        text_index=text_index,
    )
    _apply_tool_delta(delta, tool_buffers)
    _apply_usage(chunk, partial)
    return text_started


def _first_choice(chunk: dict[str, Any]) -> dict[str, Any] | None:
    """用于处理firstchoice。"""
    choices = chunk.get("choices")
    if isinstance(choices, list) and choices:
        choice = choices[0]
        return choice if isinstance(choice, dict) else None
    return None


def _apply_text_delta(
    *,
    delta: dict[str, Any],
    partial: AssistantMessage,
    queue: asyncio.Queue[AssistantMessageEvent | None],
    text_buffer: list[str],
    text_started: bool,
    text_index: int,
) -> bool:
    """用于应用文本增量。"""
    content = delta.get("content")
    if not isinstance(content, str) or not content:
        return text_started
    if not text_started:
        partial.content.append(TextContent())
        queue.put_nowait(StreamTextStartEvent(content_index=text_index, partial=partial))
        text_started = True
    text_block = partial.content[text_index]
    if isinstance(text_block, TextContent):
        text_block.text += content
    text_buffer.append(content)
    queue.put_nowait(
        StreamTextDeltaEvent(
            content_index=text_index,
            delta=content,
            partial=partial,
        )
    )
    return text_started


def _apply_tool_delta(
    delta: dict[str, Any],
    tool_buffers: dict[int, dict[str, Any]],
) -> None:
    """用于应用工具增量。"""
    tool_calls = delta.get("tool_calls")
    if not isinstance(tool_calls, list):
        return
    for raw_call in tool_calls:
        if not isinstance(raw_call, dict):
            continue
        index = int(raw_call.get("index") or 0)
        buffer = tool_buffers.setdefault(index, {"id": "", "name": "", "args": ""})
        if isinstance(raw_call.get("id"), str):
            buffer["id"] += raw_call["id"]
        function = raw_call.get("function")
        if not isinstance(function, dict):
            continue
        if isinstance(function.get("name"), str):
            buffer["name"] += function["name"]
        if isinstance(function.get("arguments"), str):
            buffer["args"] += function["arguments"]


def _emit_tool_calls(
    tool_buffers: dict[int, dict[str, Any]],
    partial: AssistantMessage,
    queue: asyncio.Queue[AssistantMessageEvent | None],
) -> None:
    """用于发送工具calls。"""
    for index in sorted(tool_buffers):
        raw_call = tool_buffers[index]
        tool_call = ToolCall(
            id=raw_call.get("id") or f"tool_{index}",
            name=raw_call.get("name") or "",
            arguments=_parse_tool_arguments(raw_call.get("args")),
        )
        content_index = len(partial.content)
        partial.content.append(tool_call)
        queue.put_nowait(
            StreamToolCallStartEvent(content_index=content_index, partial=partial)
        )
        queue.put_nowait(
            StreamToolCallEndEvent(
                content_index=content_index,
                tool_call=tool_call,
                partial=partial,
            )
        )


def _parse_tool_arguments(raw: Any) -> dict[str, Any]:
    """用于解析工具arguments。"""
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return {}
    parsed = json.loads(raw)
    return parsed if isinstance(parsed, dict) else {}


def _apply_usage(chunk: dict[str, Any], partial: AssistantMessage) -> None:
    """用于应用用量。"""
    usage = chunk.get("usage")
    if not isinstance(usage, dict):
        return
    partial.usage = Usage(
        input=int(usage.get("prompt_tokens") or 0),
        output=int(usage.get("completion_tokens") or 0),
        total_tokens=int(usage.get("total_tokens") or 0),
    )


def _finish_reason(chunk: dict[str, Any], current: str) -> str:
    """用于完成原因。"""
    choice = _first_choice(chunk)
    if not choice:
        return current
    reason = choice.get("finish_reason")
    return reason if isinstance(reason, str) and reason else current


def _stop_reason(finish_reason: str) -> StopReason:
    """用于处理stop原因。"""
    if finish_reason == "length":
        return "length"
    return "stop"


def _cancelled(options: SimpleStreamOptions) -> bool:
    """用于处理取消状态。"""
    return bool(options.cancel_event and options.cancel_event.is_set())


__all__ = ["stream_openrouter", "OpenRouterHTTPError"]
