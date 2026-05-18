"""用于覆盖 Resume Agent runtime 边界和工具 profile 行为。"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pi_agent_core import (
    AssistantMessage,
    TextContent,
    ToolCall,
    ToolExecutionStartEvent,
    ToolResultMessage,
    UserMessage,
)

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.resume.agent import ResumeAgent  # noqa: E402
from app.runtime import pi_agent_runtime  # noqa: E402
from app.runtime.message_conversion import convert_resume_messages_to_llm  # noqa: E402
from app.runtime.openrouter_adapter import build_openrouter_config  # noqa: E402
from app.runtime.pi_agent_runtime import PiAgentRuntime  # noqa: E402
from app.runtime.resume_agent_session import (  # noqa: E402
    ResumeAgentSession,
    maybe_compact_resume_context,
)
from app.runtime.tool_confirmation import ToolConfirmationPolicy  # noqa: E402


def _build_runtime_inputs(agent: ResumeAgent, user_message: str) -> tuple[Any, dict[str, Any]]:
    """用于生成最小 runtime 输入并返回 pi_context 和 state。"""
    state = agent.runtime._new_stream_state()
    context = {
        "resume_content": {"projects": [{"id": "proj_1", "name": "Chat Resume"}]},
    }
    pi_context, _prompts, _config = agent.runtime._build_loop_inputs(
        agent=agent.definition,
        user_message=user_message,
        context=context,
        conversation_history=[],
        run_id="run_test",
        confirmation_queue=None,
        event_queue=None,
        event_callback=None,
        executed_tools=[],
        stream_state=state,
    )
    return pi_context, state


def test_plain_message_exposes_resume_tools_for_model_choice():
    """用于验证普通消息也由模型自行决定是否调用工具。"""
    agent = ResumeAgent()

    pi_context, state = _build_runtime_inputs(agent, "这份简历有哪些问题？")

    assert state["tool_profile"] == "resume_edit"
    assert {tool.name for tool in pi_context.tools} == {
        "update_overview",
        "update_bullet",
        "add_bullet",
        "remove_bullet",
        "generate_job_match_summary",
    }


def test_system_prompt_does_not_mirror_active_tools():
    """用于验证系统提示词不再镜像实际暴露给模型的工具。"""
    agent = ResumeAgent()

    pi_context, state = _build_runtime_inputs(agent, "优化项目经历")

    assert "## 可用工具" not in pi_context.system_prompt
    assert "update_bullet" not in pi_context.system_prompt
    assert "generate_job_match_summary" not in pi_context.system_prompt
    assert state["tool_names"] == [
        "update_overview",
        "update_bullet",
        "add_bullet",
        "remove_bullet",
        "generate_job_match_summary",
    ]


def test_system_prompt_template_omits_tool_summary_variables():
    """用于验证 system.md 不保留工具摘要占位。"""
    prompt_path = BACKEND_DIR / "app" / "prompts" / "resume_agent" / "system.md"
    raw_prompt = prompt_path.read_text(encoding="utf-8")

    assert "edit_tools_available" not in raw_prompt
    assert "job_match_tool_available" not in raw_prompt
    assert "default(true)" not in raw_prompt
    assert "{{" not in raw_prompt
    assert "${available_tools}" not in raw_prompt
    assert "${tool_usage_rules}" not in raw_prompt
    assert "${tool_protocol}" not in raw_prompt
    assert "首轮" not in raw_prompt


def test_system_prompt_tool_list_matches_requested_profile():
    """用于验证工具摘要随当前工具 profile 更新。"""
    agent = ResumeAgent()
    state = agent.runtime._new_stream_state()
    context = {
        "resume_content": {"projects": [{"id": "proj_1", "name": "Chat Resume"}]},
        "tool_profile": "read_only",
    }

    pi_context, _prompts, _config = agent.runtime._build_loop_inputs(
        agent=agent.definition,
        user_message="只分析，不要修改",
        context=context,
        conversation_history=[],
        run_id="run_test",
        confirmation_queue=None,
        event_queue=None,
        event_callback=None,
        executed_tools=[],
        stream_state=state,
    )

    assert [tool.name for tool in pi_context.tools] == ["generate_job_match_summary"]
    assert "generate_job_match_summary" not in pi_context.system_prompt
    assert "update_bullet" not in pi_context.system_prompt


def test_job_match_message_still_exposes_resume_tools_for_model_choice():
    """用于验证岗位匹配消息不再由后端收窄工具集。"""
    agent = ResumeAgent()

    pi_context, state = _build_runtime_inputs(agent, "这个 JD 的岗位匹配度怎么样？")

    assert state["tool_profile"] == "resume_edit"
    assert {tool.name for tool in pi_context.tools} == {
        "update_overview",
        "update_bullet",
        "add_bullet",
        "remove_bullet",
        "generate_job_match_summary",
    }


def test_llm_request_event_records_profile_counts_and_prompt_size():
    """用于验证 LLM 请求日志字段包含 profile、工具数量和 prompt 信息。"""
    agent = ResumeAgent()
    pi_context, state = _build_runtime_inputs(agent, "优化项目经历")

    event = agent.runtime._llm_request_event(agent.definition, pi_context, [], state)

    assert event["tool_profile"] == "resume_edit"
    assert event["tool_count"] == 5
    assert event["message_count"] == 1
    assert event["prompt_chars"] > 0


def test_llm_response_event_records_first_token_usage_and_confirmation_wait():
    """用于验证 LLM 响应日志字段包含首 token、usage 和确认等待耗时。"""
    agent = ResumeAgent()
    state = agent.runtime._new_stream_state()
    state["first_token_latency_ms"] = 12.5
    state["confirmation_wait_ms"] = 30.0
    state["usage"] = {"input": 10, "output": 5, "total_tokens": 15}

    event = agent.runtime._llm_response_event(agent.definition, state)

    assert event["first_token_latency_ms"] == 12.5
    assert event["confirmation_wait_ms"] == 30.0
    assert event["usage"]["total_tokens"] == 15


def test_allowed_tool_call_uses_normal_detection_trace(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
):
    """用于验证默认工具集下模型工具调用不再被判为 unexpected。"""
    agent = ResumeAgent()
    state = agent.runtime._new_stream_state()
    state["tool_profile"] = "resume_edit"
    state["tool_names"] = ["update_bullet"]
    event = ToolExecutionStartEvent(
        tool_call_id="call_1",
        tool_name="update_bullet",
        args={},
    )
    monkeypatch.setattr(pi_agent_runtime.settings, "AGENT_TRACE_LOG_ENABLED", True)

    with caplog.at_level("INFO", logger="app.runtime.pi_agent_runtime"):
        agent.runtime._trace_tool_call_detected(agent.definition, "run_test", event, state)
        agent.runtime._trace_tool_call_detected(agent.definition, "run_test", event, state)

    messages = [record.getMessage() for record in caplog.records]
    assert "agent.trace.reasoning.unexpected_tool_call" not in messages
    assert messages.count("agent.trace.reasoning.tool_call_detected") == 2


def test_failed_tool_preview_logs_warning(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
):
    """用于验证工具预览失败在日志里更醒目。"""
    agent = ResumeAgent()
    monkeypatch.setattr(pi_agent_runtime.settings, "AGENT_TRACE_LOG_ENABLED", True)

    with caplog.at_level("INFO", logger="app.runtime.pi_agent_runtime"):
        agent.runtime._trace_tool_preview(
            agent.definition,
            "run_test",
            "call_preview",
            "update_bullet",
            {
                "tool_name": "优化要点",
                "display_message": "update_bullet 缺少必填参数: section",
                "result": {"success": False, "error": "missing section"},
            },
        )

    preview_record = next(
        record
        for record in caplog.records
        if record.getMessage() == "agent.trace.tool.preview_failed"
    )
    assert preview_record.levelno == logging.WARNING
    assert getattr(preview_record, "tool_name") == "update_bullet"
    assert getattr(preview_record, "result_success") is False


def test_tool_requested_trace_summarizes_large_text_input(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
):
    """用于验证工具请求日志只记录可读摘要而不是完整文本。"""
    agent = ResumeAgent()
    long_text = "基于 LlamaIndex 构建文档索引与向量存储层，支撑 RAG 检索。" * 8
    monkeypatch.setattr(pi_agent_runtime.settings, "AGENT_TRACE_LOG_ENABLED", True)

    with caplog.at_level("INFO", logger="app.runtime.pi_agent_runtime"):
        agent.runtime._trace_tool_requested(
            agent.definition,
            "run_test",
            "call_requested",
            "add_bullet",
            {
                "item_id": "proj_1",
                "reason": "补充 JD 要求的 LlamaIndex 技术栈，强化 RAG 向量检索能力",
                "section": "projects",
                "text": long_text,
            },
            True,
        )

    requested_record = next(
        record
        for record in caplog.records
        if record.getMessage() == "agent.trace.tool.requested"
    )
    tool_input = getattr(requested_record, "tool_input")
    assert tool_input["item_id"] == "proj_1"
    assert tool_input["section"] == "projects"
    assert tool_input["text_chars"] == len(long_text)
    assert tool_input["text_preview"].startswith("基于 LlamaIndex")
    assert "text" not in tool_input


def test_convert_resume_messages_filters_internal_only_messages():
    """用于验证 convert_to_llm 不会把 UI 或内部事件送进模型。"""
    user = UserMessage(content=[TextContent(text="用户问题")])
    assistant = AssistantMessage(content=[TextContent(text="助手回答")])
    tool_result = ToolResultMessage(
        tool_call_id="call_1",
        tool_name="read_resume",
        content=[TextContent(text="结果")],
    )
    internal = SimpleNamespace(role="ui", content=[TextContent(text="只给 UI")])

    converted = convert_resume_messages_to_llm([user, assistant, tool_result, internal])

    assert converted == [user, assistant, tool_result]


@pytest.mark.asyncio
async def test_confirmation_policy_returns_feedback_without_terminating_turn():
    """用于验证确认 hook 将确认结果交还给模型继续 ReAct。"""
    policy = ToolConfirmationPolicy()
    queue: asyncio.Queue[bool] = asyncio.Queue()

    decision = policy.before_tool_call(
        confirmation_queue=queue,
        tool_name="update_bullet",
        auto_execute_tool_names=set(),
    )
    queue.put_nowait(False)
    confirmed = await policy.wait_for_decision(queue)
    result = policy.after_tool_decision(confirmed=confirmed)

    assert decision.requires_confirmation is True
    assert result.confirmed is False
    assert result.terminate_turn is False


def test_openrouter_adapter_preserves_business_model_defaults():
    """用于验证 provider 配置从 runtime 中拆出且保留模型默认值。"""
    agent = ResumeAgent()

    config = build_openrouter_config(agent.definition)

    assert config.model.provider == "openrouter"
    assert config.model.api == "openai-compatible"
    assert config.temperature == agent.prompt_spec.model_defaults["temperature"]
    assert config.max_tokens == agent.prompt_spec.model_defaults["max_tokens"]


def test_long_resume_context_compacts_with_jd_and_confirmed_changes():
    """用于验证长简历上下文摘要保留 JD 和已确认改动。"""
    resume = {
        "job_application": {"jd_text": "需要 Python、Agent、性能优化"},
        "projects": [
            {
                "id": "proj_1",
                "name": "Chat Resume",
                "overview": "负责 Agent 简历优化" * 300,
                "highlights": [{"id": "hl_1", "text": "实现流式优化"}],
            }
        ],
    }

    compacted = maybe_compact_resume_context(
        resume_content=resume,
        confirmed_diff_items=[
            {"before": "实现流式优化", "after": "实现低延迟流式优化", "reason": "突出性能"}
        ],
        conversation_history=[{"role": "user", "content": "优化项目"}],
        threshold_chars=100,
    )

    assert compacted["summary_mode"] is True
    assert "性能优化" in compacted["jd_text"]
    assert "低延迟" in compacted["confirmed_changes"][0]
    assert compacted["resume_snapshot"]["projects"][0]["id"] == "proj_1"


def test_resume_agent_session_rebuilds_transcript_model_and_summary():
    """用于验证业务版 ResumeAgentSession 可从事件重建下一轮上下文。"""
    events = [
        SimpleNamespace(
            event_type="user_message",
            payload={"content": "优化项目"},
        ),
        SimpleNamespace(
            event_type="stream_event",
            payload={
                "event_type": "llm_request",
                "model": "openrouter/test",
                "tool_profile": "resume_edit",
                "tool_names": ["update_bullet"],
            },
        ),
        SimpleNamespace(
            event_type="tool_call_previewed",
            payload={"tool_call": {"id": "call_1"}},
        ),
        SimpleNamespace(
            event_type="agent_response",
            payload={"content": "已完成优化。"},
        ),
        SimpleNamespace(
            event_type="stream_event",
            payload={
                "event_type": "llm_response",
                "usage": {"input": 1, "output": 2, "total_tokens": 3},
            },
        ),
    ]

    session = ResumeAgentSession.from_events(
        events,
        resume_content={"projects": [{"id": "proj_1", "name": "Chat Resume"}]},
    )

    assert session.to_conversation_history() == [
        {"role": "user", "content": "优化项目"},
        {"role": "assistant", "content": "已完成优化。"},
    ]
    assert session.model_config is not None
    assert session.model_config.tool_profile == "resume_edit"
    assert session.pending_tool_call == {"id": "call_1"}
    assert session.usage["total_tokens"] == 3


# ---------------------------------------------------------------------------
# Fake tool-call guard tests
# ---------------------------------------------------------------------------

def _make_stream_fn(responses: list[AssistantMessage]):
    """构造确定性假 stream 函数，依次返回预设响应。"""
    calls = {"count": 0}

    def stream_fn(model: Any, context: Any, options: Any) -> dict[str, Any]:
        idx = calls["count"]
        calls["count"] += 1
        message = responses[idx]

        async def events():
            for block in message.content:
                if isinstance(block, TextContent) and block.text:
                    yield SimpleNamespace(type="text_delta", delta=block.text)
            # tool calls are conveyed via the result message, not streaming events

        async def result():
            return message

        return {"events": events(), "result": result}

    return stream_fn, calls


async def _run_react_loop_async(
    runtime: PiAgentRuntime,
    agent: ResumeAgent,
    responses: list[AssistantMessage],
    user_message: str = "优化项目经历",
    confirmation_queue: asyncio.Queue | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """异步运行 _run_react_loop 并返回 (events, 调用次数) 元组。"""
    stream_fn, call_tracker = _make_stream_fn(responses)
    runtime_with_fn = PiAgentRuntime(stream_fn=stream_fn)

    state = runtime_with_fn._new_stream_state()
    context: dict[str, Any] = {
        "resume_content": {
            "projects": [{"id": "proj_1", "name": "Chat Resume",
                           "highlights": [{"id": "hl_1", "text": "旧描述"}]}]
        }
    }
    pi_context, prompts, config = runtime_with_fn._build_loop_inputs(
        agent=agent.definition,
        user_message=user_message,
        context=context,
        conversation_history=[],
        run_id="test_guard_run",
        confirmation_queue=confirmation_queue,
        event_queue=None,
        event_callback=None,
        executed_tools=[],
        stream_state=state,
    )
    event_queue: asyncio.Queue[Any] = asyncio.Queue()
    await runtime_with_fn._run_react_loop(
        agent=agent.definition,
        run_id="test_guard_run",
        pi_context=pi_context,
        prompts=prompts,
        config=config,
        context=context,
        confirmation_queue=confirmation_queue,
        event_queue=event_queue,
        event_callback=None,
        state=state,
        executed_tools=[],
    )
    events: list[dict[str, Any]] = []
    while not event_queue.empty():
        events.append(event_queue.get_nowait())
    return events, call_tracker["count"]


@pytest.mark.asyncio
async def test_fake_tool_claim_text_not_published_to_event_queue(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
):
    """tool_calls=[] 但文本声称已修改时，该文本不发布给用户，触发修复轮次。"""
    monkeypatch.setattr(pi_agent_runtime.settings, "AGENT_TRACE_LOG_ENABLED", True)
    fake_text = "我已修改了你的项目描述，增加了量化指标。"
    repair_text = "明白了，本轮我不会修改简历，你有什么问题请告诉我。"

    responses = [
        AssistantMessage(content=[TextContent(text=fake_text)], stop_reason="stop"),
        AssistantMessage(content=[TextContent(text=repair_text)], stop_reason="stop"),
    ]

    with caplog.at_level("INFO", logger="app.runtime.pi_agent_runtime"):
        events, call_count = await _run_react_loop_async(PiAgentRuntime(), ResumeAgent(), responses)

    text_published = "".join(e.get("content", "") for e in events if e.get("event_type") == "text_delta")
    assert fake_text not in text_published
    assert repair_text in text_published
    assert call_count == 2

    log_messages = [r.getMessage() for r in caplog.records]
    assert "agent.trace.reasoning.tool_intent_without_call" in log_messages


@pytest.mark.asyncio
async def test_repair_turn_real_tool_call_produces_tool_pending(
    monkeypatch: pytest.MonkeyPatch,
):
    """修复轮次返回真实 tool_call 时，现有确认门仍正常产出 tool_pending 事件。"""
    fake_text = "已修改简历中的项目描述。"
    tool_call = ToolCall(
        id="call_repair_tc_1",
        name="update_bullet",
        arguments={
            "section": "projects",
            "item_id": "proj_1",
            "bullet_id": "hl_1",
            "text": "优化后的描述",
        },
    )
    final_text = "已通过真实工具完成修改。"

    responses = [
        AssistantMessage(content=[TextContent(text=fake_text)], stop_reason="stop"),
        AssistantMessage(content=[tool_call], stop_reason="toolUse"),
        AssistantMessage(content=[TextContent(text=final_text)], stop_reason="stop"),
    ]

    agent = ResumeAgent()
    agent.definition.tool_executor = lambda tc, ctx: {
        "tool_name": "优化要点",
        "display_message": "已更新",
        "result": {"success": True, "diff_summary": "测试修改", "diff_items": []},
    }

    confirmation_queue: asyncio.Queue[bool] = asyncio.Queue()
    confirmation_queue.put_nowait(True)

    events, call_count = await _run_react_loop_async(
        PiAgentRuntime(), agent, responses, confirmation_queue=confirmation_queue
    )

    event_types = [e.get("event_type") for e in events]
    assert "tool_pending" in event_types
    assert call_count == 3


@pytest.mark.asyncio
async def test_pure_consultation_text_not_intercepted_by_guard(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
):
    """纯咨询文本且无工具声称时，守卫不触发，文本正常发布。"""
    monkeypatch.setattr(pi_agent_runtime.settings, "AGENT_TRACE_LOG_ENABLED", True)
    consult_text = "你的简历结构清晰，建议在项目经历中补充量化数据以增强说服力。"

    responses = [
        AssistantMessage(content=[TextContent(text=consult_text)], stop_reason="stop"),
    ]

    with caplog.at_level("INFO", logger="app.runtime.pi_agent_runtime"):
        events, call_count = await _run_react_loop_async(PiAgentRuntime(), ResumeAgent(), responses)

    text_published = "".join(e.get("content", "") for e in events if e.get("event_type") == "text_delta")
    assert consult_text in text_published
    assert call_count == 1

    log_messages = [r.getMessage() for r in caplog.records]
    assert "agent.trace.reasoning.tool_intent_without_call" not in log_messages


@pytest.mark.asyncio
async def test_fake_tool_intent_log_contains_required_fields(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
):
    """日志 agent.trace.reasoning.tool_intent_without_call 包含所有定位字段。"""
    monkeypatch.setattr(pi_agent_runtime.settings, "AGENT_TRACE_LOG_ENABLED", True)
    fake_text = "我来调用 update_bullet 修改你的项目描述。"

    responses = [
        AssistantMessage(content=[TextContent(text=fake_text)], stop_reason="stop"),
        AssistantMessage(content=[TextContent(text="好的，请问你想修改哪个要点？")], stop_reason="stop"),
    ]

    with caplog.at_level("INFO", logger="app.runtime.pi_agent_runtime"):
        await _run_react_loop_async(PiAgentRuntime(), ResumeAgent(), responses)

    guard_record = next(
        (r for r in caplog.records if r.getMessage() == "agent.trace.reasoning.tool_intent_without_call"),
        None,
    )
    assert guard_record is not None
    assert getattr(guard_record, "run_id", None) is not None
    assert getattr(guard_record, "tool_profile", None) is not None
    assert getattr(guard_record, "available_tool_names", None) is not None
    assert getattr(guard_record, "text_preview", None) is not None
    assert getattr(guard_record, "repair_attempted") is True
