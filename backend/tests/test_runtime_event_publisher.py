"""用于覆盖 RuntimeEventPublisher 的事件契约。"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from pi_agent_core import (
    AgentContext,
    AgentTool,
    AgentToolResult,
    AgentToolSchema,
    TextContent,
    UserMessage,
)

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.resume.agent import ResumeAgent  # noqa: E402
from app.runtime.runtime_event_adapter import RuntimeEventPublisher  # noqa: E402
from app.types.stream import ResumeStreamEvent  # noqa: E402


async def _fake_tool_execute(**_kwargs: Any) -> AgentToolResult:
    """用于提供符合 pi-agent-core 类型的测试工具执行函数。"""
    return AgentToolResult(content=[TextContent(text="ok")])


def test_runtime_event_publisher_builds_llm_request_event():
    """用于验证 LLM request 事件由 publisher 统一生成。"""
    agent = ResumeAgent()
    publisher = RuntimeEventPublisher(chat_model_name=lambda: "test-model")
    state = publisher.new_stream_state()
    state["tool_profile"] = "resume_edit"
    state["prompt_chars"] = 123
    context = AgentContext(
        system_prompt="system prompt",
        messages=[UserMessage(content=[TextContent(text="用户问题")])],
        tools=[
            AgentTool(
                name="update_bullet",
                description="update",
                parameters=AgentToolSchema(),
                execute=_fake_tool_execute,
            )
        ],
    )

    event = publisher.llm_request(agent.definition, context, [], state)

    assert event["event_type"] == "llm_request"
    assert event["agent_name"] == "resume_agent"
    assert event["model"] == "test-model"
    assert event["message_count"] == 2
    assert event["tool_count"] == 1
    assert event["tool_profile"] == "resume_edit"
    assert event["prompt_chars"] == 123
    assert event["messages"][0] == {"role": "system", "content": "system prompt"}


def test_runtime_event_publisher_builds_llm_response_event():
    """用于验证 LLM response 事件从 stream state 统一转换。"""
    agent = ResumeAgent()
    publisher = RuntimeEventPublisher(chat_model_name=lambda: "test-model")
    state = publisher.new_stream_state()
    state["response_parts"] = ["你好", "，已完成"]
    state["tool_call_count"] = 2
    state["first_token_latency_ms"] = 12.5
    state["confirmation_wait_ms"] = 30.0
    state["usage"] = {"input": 10, "output": 5, "total_tokens": 15}

    event = publisher.llm_response(agent.definition, state)

    assert event["event_type"] == "llm_response"
    assert event["response_content"] == "你好，已完成"
    assert event["tool_call_count"] == 2
    assert event["first_token_latency_ms"] == 12.5
    assert event["confirmation_wait_ms"] == 30.0
    assert event["usage"]["total_tokens"] == 15
    assert event["latency_ms"] >= 0


def test_runtime_event_publisher_builds_tool_events():
    """用于验证工具可见事件也由 publisher 统一生成。"""
    publisher = RuntimeEventPublisher(chat_model_name=lambda: "test-model")
    tool_call = {
        "id": "call_1",
        "type": "function",
        "function": {"name": "update_bullet", "arguments": {"text": "改写"}},
    }

    started = publisher.tool_call_started(
        call_id="call_1",
        tool_name="update_bullet",
        tool_call=tool_call,
        tool_input={"text": "改写"},
    )
    result = publisher.tool_result(
        call_id="call_1",
        tool_name="update_bullet",
        tool_display_name="修改要点",
        tool_calls=[{"name": "修改要点"}],
        result={"success": True},
        display_message="已修改",
        context={"resume_content": {}},
    )

    assert started["event_type"] == "tool_call"
    assert started["tool_id"] == "update_bullet"
    assert started["tool_display_name"] == "update_bullet"
    assert result["event_type"] == "tool_result"
    assert result["tool_id"] == "update_bullet"
    assert result["tool_display_name"] == "修改要点"


@pytest.mark.asyncio
async def test_runtime_event_publisher_publish_emits_callback_and_queue():
    """用于验证 publisher 统一处理 callback 和 queue 发布。"""
    publisher = RuntimeEventPublisher(chat_model_name=lambda: "test-model")
    queue: asyncio.Queue[Any] = asyncio.Queue()
    emitted: list[Mapping[str, Any]] = []
    event: ResumeStreamEvent = {"event_type": "text_delta", "content": "hi", "done": False}

    await publisher.publish(
        event_queue=queue,
        event_callback=emitted.append,
        event=event,
    )

    assert emitted == [event]
    assert await queue.get() == event
