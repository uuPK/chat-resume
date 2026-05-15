"""用于覆盖 ReActTurnRunner 的单轮调度行为。"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, cast

import pytest
from pi_agent_core import (
    AgentContext,
    AgentToolResult,
    AssistantMessage,
    StreamDoneEvent,
    StreamStartEvent,
    StreamTextDeltaEvent,
    StreamTextEndEvent,
    StreamTextStartEvent,
    TextContent,
    ToolCall,
    ToolResultMessage,
    UserMessage,
)
from pi_agent_core.types import StreamFn, StreamResult

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.resume.agent import ResumeAgent  # noqa: E402
from app.infra.config import settings  # noqa: E402
from app.runtime.message_conversion import convert_resume_messages_to_llm  # noqa: E402
from app.runtime.openrouter_adapter import build_openrouter_loop_config  # noqa: E402
from app.runtime.react_turn_runner import ReActTurnRunner  # noqa: E402
from app.runtime.runtime_event_adapter import RuntimeEventPublisher  # noqa: E402
from app.runtime.tool_execution_pipeline import ToolExecutionPipeline  # noqa: E402
from app.runtime.trace_recorder import DefaultTraceRecorder  # noqa: E402


class FakePiAgentStream:
    """用于给 ReActTurnRunner 提供确定性的模型响应。"""

    def __init__(self, messages: list[AssistantMessage]):
        """保存预设响应。"""
        self.messages = list(messages)
        self.contexts: list[AgentContext] = []
        self.calls = 0

    async def __call__(self, model: Any, context: AgentContext, options: Any) -> StreamResult:
        """返回 pi-agent-core stream 函数协议。"""
        del model, options
        self.contexts.append(context)
        message = self.messages[self.calls]
        self.calls += 1

        async def events_iter():
            """逐个返回当前 assistant message 对应事件。"""
            for event in _events_for(message):
                yield event

        async def result() -> AssistantMessage:
            """返回当前完整 assistant message。"""
            return message

        return cast(StreamResult, {"events": events_iter(), "result": result})


class FakeToolPipeline:
    """用于记录 runner 发起的工具调用并返回固定结果。"""

    def __init__(self):
        """初始化调用记录。"""
        self.calls: list[dict[str, Any]] = []

    async def execute_tool_result(self, **kwargs: Any) -> AgentToolResult:
        """记录工具调用并返回可追加到 ReAct 消息链的结果。"""
        self.calls.append(kwargs)
        kwargs["executed_tools"].append(
            {"name": kwargs["tool_name"], "result": "ok", "success": True}
        )
        return AgentToolResult(
            content=[TextContent(text='{"success": true}')],
            details='{"success": true}',
        )


def _events_for(message: AssistantMessage) -> list[Any]:
    """把完整 assistant message 转成最小流式事件。"""
    events: list[Any] = [StreamStartEvent(partial=message)]
    for index, block in enumerate(message.content):
        if isinstance(block, TextContent):
            events.extend(
                [
                    StreamTextStartEvent(content_index=index, partial=message),
                    StreamTextDeltaEvent(
                        content_index=index,
                        delta=block.text,
                        partial=message,
                    ),
                    StreamTextEndEvent(
                        content_index=index,
                        content=block.text,
                        partial=message,
                    ),
                ]
            )
    events.append(StreamDoneEvent(reason=message.stop_reason, message=message))
    return events


def _text_message(text: str) -> AssistantMessage:
    """构造文本 assistant message。"""
    return AssistantMessage(content=[TextContent(text=text)], stop_reason="stop")


def _tool_message(call_id: str = "call_1") -> AssistantMessage:
    """构造工具调用 assistant message。"""
    return AssistantMessage(
        content=[ToolCall(id=call_id, name="update_bullet", arguments={"text": "新要点"})],
        stop_reason="toolUse",
    )


def _runner(stream: FakePiAgentStream, pipeline: FakeToolPipeline) -> ReActTurnRunner:
    """构造带 fake LLM 和 fake tool pipeline 的 runner。"""
    return ReActTurnRunner(
        stream_fn=cast(StreamFn, stream),
        tool_pipeline=cast(ToolExecutionPipeline, pipeline),
        event_publisher=RuntimeEventPublisher(),
        trace_recorder=DefaultTraceRecorder(),
    )


def _state() -> dict[str, Any]:
    """构造测试用 stream state。"""
    state = RuntimeEventPublisher.new_stream_state()
    state["tool_names"] = ["update_bullet"]
    return state


def _loop_inputs(agent: ResumeAgent) -> tuple[AgentContext, list[Any], Any]:
    """构造 runner 需要的最小 loop 输入。"""
    pi_context = AgentContext(system_prompt="system", messages=[], tools=[])
    prompts = [UserMessage(content=[TextContent(text="优化简历")])]
    config = build_openrouter_loop_config(
        agent.definition,
        convert_to_llm=convert_resume_messages_to_llm,
    )
    return pi_context, prompts, config


@pytest.mark.asyncio
async def test_react_turn_runner_publishes_single_text_turn():
    """用于验证单轮无工具响应会发布文本并停止。"""
    agent = ResumeAgent()
    stream = FakePiAgentStream([_text_message("你好")])
    pipeline = FakeToolPipeline()
    runner = _runner(stream, pipeline)
    pi_context, prompts, config = _loop_inputs(agent)
    state = _state()

    await runner.run_loop(
        agent=agent.definition,
        run_id="run_text",
        pi_context=pi_context,
        prompts=prompts,
        config=config,
        context={},
        confirmation_queue=None,
        event_queue=None,
        event_callback=None,
        state=state,
        executed_tools=[],
    )

    assert stream.calls == 1
    assert state["response_parts"] == ["你好"]
    assert pipeline.calls == []


@pytest.mark.asyncio
async def test_react_turn_runner_roundtrips_tool_result_to_next_turn():
    """用于验证工具结果会回填到下一轮模型上下文。"""
    agent = ResumeAgent()
    stream = FakePiAgentStream([_tool_message(), _text_message("已完成")])
    pipeline = FakeToolPipeline()
    runner = _runner(stream, pipeline)
    pi_context, prompts, config = _loop_inputs(agent)
    state = _state()
    executed_tools: list[dict[str, Any]] = []

    await runner.run_loop(
        agent=agent.definition,
        run_id="run_tool",
        pi_context=pi_context,
        prompts=prompts,
        config=config,
        context={},
        confirmation_queue=None,
        event_queue=None,
        event_callback=None,
        state=state,
        executed_tools=executed_tools,
    )

    assert stream.calls == 2
    assert executed_tools == [{"name": "update_bullet", "result": "ok", "success": True}]
    assert state["response_parts"] == ["已完成"]
    second_turn_messages = stream.contexts[1].messages
    assert any(
        isinstance(message, ToolResultMessage) and message.tool_call_id == "call_1"
        for message in second_turn_messages
    )


@pytest.mark.asyncio
async def test_react_turn_runner_stops_at_max_iterations(caplog: pytest.LogCaptureFixture):
    """用于验证 max_iterations 命中后 runner 记录终止原因并停止。"""
    agent = ResumeAgent()
    agent.definition.max_iterations = 1
    stream = FakePiAgentStream([_tool_message()])
    pipeline = FakeToolPipeline()
    runner = _runner(stream, pipeline)
    pi_context, prompts, config = _loop_inputs(agent)
    state = _state()
    original_trace_enabled = settings.AGENT_TRACE_LOG_ENABLED
    settings.AGENT_TRACE_LOG_ENABLED = True

    try:
        with caplog.at_level("INFO", logger="app.runtime.pi_agent_runtime"):
            await runner.run_loop(
                agent=agent.definition,
                run_id="run_limit",
                pi_context=pi_context,
                prompts=prompts,
                config=config,
                context={},
                confirmation_queue=None,
                event_queue=None,
                event_callback=None,
                state=state,
                executed_tools=[],
            )
    finally:
        settings.AGENT_TRACE_LOG_ENABLED = original_trace_enabled

    assert stream.calls == 1
    assert [record.getMessage() for record in caplog.records].count(
        "agent.trace.run.max_iterations_reached"
    ) == 1
