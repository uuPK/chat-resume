"""用于覆盖 PiAgentRuntime 工具执行 pipeline。"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.resume.agent import ResumeAgent  # noqa: E402
from app.runtime.runtime_event_adapter import RuntimeEventPublisher  # noqa: E402
from app.runtime.tool_execution_pipeline import ToolExecutionPipeline  # noqa: E402


def _update_bullet_schema() -> list[dict[str, Any]]:
    """用于生成最小可执行工具 schema。"""
    return [
        {
            "type": "function",
            "function": {
                "name": "update_bullet",
                "description": "更新要点",
                "parameters": {
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
            },
        }
    ]


def _make_pipeline() -> ToolExecutionPipeline:
    """用于创建测试 pipeline。"""
    return ToolExecutionPipeline(
        event_publisher=RuntimeEventPublisher(chat_model_name=lambda: "test-model"),
    )


@pytest.mark.asyncio
async def test_tool_pipeline_confirms_and_executes_tool():
    """用于验证工具 pipeline 支持 pending -> confirmed -> executed。"""
    agent = ResumeAgent()
    calls: list[dict[str, Any]] = []

    def tool_executor(tool_call: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """用于区分 preview 和实际执行上下文。"""
        calls.append({"tool_call": tool_call, "context": context})
        return {
            "tool_name": "修改要点",
            "display_message": "已更新要点",
            "result": {
                "success": True,
                "diff_summary": "补充业务规模",
                "diff_items": [{"before": "旧", "after": "新"}],
            },
        }

    agent.definition.tool_executor = tool_executor
    queue: asyncio.Queue[bool] = asyncio.Queue()
    queue.put_nowait(True)
    event_queue: asyncio.Queue[Any] = asyncio.Queue()
    executed_tools: list[dict[str, Any]] = []
    stream_state = RuntimeEventPublisher.new_stream_state()
    pipeline = _make_pipeline()
    tools = pipeline.build_tools(
        agent=agent.definition,
        tools_schema=_update_bullet_schema(),
        context={"resume_content": {"work_experience": []}},
        confirmation_queue=queue,
        event_queue=event_queue,
        event_callback=None,
        run_id="run_1",
        executed_tools=executed_tools,
        stream_state=stream_state,
    )

    result = await tools[0].execute(tool_call_id="call_1", params={"text": "新"})

    assert json.loads(result.details)["success"] is True
    assert executed_tools == [{"name": "修改要点", "result": "补充业务规模", "success": True}]
    assert stream_state["confirmed_diff_items"] == [{"before": "旧", "after": "新"}]
    assert len(calls) == 2
    events = [await event_queue.get() for _ in range(event_queue.qsize())]
    assert [event["event_type"] for event in events] == [
        "tool_call",
        "tool_pending",
        "tool_confirmed",
    ]


@pytest.mark.asyncio
async def test_tool_pipeline_rejects_pending_tool_without_executing_again():
    """用于验证工具 pipeline 支持 pending -> rejected。"""
    agent = ResumeAgent()
    call_count = 0

    def tool_executor(_tool_call: dict[str, Any], _context: dict[str, Any]) -> dict[str, Any]:
        """用于返回预览结果并统计是否重复执行。"""
        nonlocal call_count
        call_count += 1
        return {
            "tool_name": "修改要点",
            "display_message": "待确认修改",
            "result": {"success": True, "diff_items": [{"before": "旧", "after": "新"}]},
        }

    agent.definition.tool_executor = tool_executor
    queue: asyncio.Queue[bool] = asyncio.Queue()
    queue.put_nowait(False)
    event_queue: asyncio.Queue[Any] = asyncio.Queue()
    executed_tools: list[dict[str, Any]] = []
    stream_state = RuntimeEventPublisher.new_stream_state()
    pipeline = _make_pipeline()
    tools = pipeline.build_tools(
        agent=agent.definition,
        tools_schema=_update_bullet_schema(),
        context={"resume_content": {"work_experience": []}},
        confirmation_queue=queue,
        event_queue=event_queue,
        event_callback=None,
        run_id="run_1",
        executed_tools=executed_tools,
        stream_state=stream_state,
    )

    result = await tools[0].execute(tool_call_id="call_1", params={"text": "新"})

    assert json.loads(result.details) == {"success": False, "error": "用户拒绝了此修改"}
    assert executed_tools == []
    assert call_count == 1
    assert stream_state["response_parts"] == ["已取消这处修改。"]
    events = [await event_queue.get() for _ in range(event_queue.qsize())]
    assert [event["event_type"] for event in events] == [
        "tool_call",
        "tool_pending",
        "tool_rejected",
        "text_delta",
    ]


@pytest.mark.asyncio
async def test_tool_pipeline_converts_handler_exception_to_failure_result():
    """用于验证工具 handler 异常会降级为失败 ToolResult。"""
    agent = ResumeAgent()

    def tool_executor(_tool_call: dict[str, Any], _context: dict[str, Any]) -> dict[str, Any]:
        """用于模拟业务工具抛异常。"""
        raise RuntimeError("boom")

    agent.definition.tool_executor = tool_executor
    event_queue: asyncio.Queue[Any] = asyncio.Queue()
    executed_tools: list[dict[str, Any]] = []
    stream_state = RuntimeEventPublisher.new_stream_state()
    pipeline = _make_pipeline()
    tools = pipeline.build_tools(
        agent=agent.definition,
        tools_schema=_update_bullet_schema(),
        context={"resume_content": {"work_experience": []}},
        confirmation_queue=None,
        event_queue=event_queue,
        event_callback=None,
        run_id="run_1",
        executed_tools=executed_tools,
        stream_state=stream_state,
    )

    result = await tools[0].execute(tool_call_id="call_1", params={"text": "新"})
    payload = json.loads(result.details)

    assert payload["success"] is False
    assert "boom" in payload["error"]
    assert executed_tools == [{"name": "update_bullet", "result": None, "success": False}]
    events = [await event_queue.get() for _ in range(event_queue.qsize())]
    assert [event["event_type"] for event in events] == ["tool_call", "tool_call_failed"]
