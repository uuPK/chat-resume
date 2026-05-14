"""用于覆盖 Resume Agent runtime 边界和工具 profile 行为。"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pi_agent_core import AssistantMessage, TextContent, ToolResultMessage, UserMessage

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.resume.agent import ResumeAgent  # noqa: E402
from app.runtime.message_conversion import convert_resume_messages_to_llm  # noqa: E402
from app.runtime.openrouter_adapter import build_openrouter_config  # noqa: E402
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
        "tool_profile": agent._select_tool_profile(user_message),
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


def test_read_only_message_exposes_no_edit_tools():
    """用于验证只读问题不会暴露简历编辑工具。"""
    agent = ResumeAgent()

    pi_context, state = _build_runtime_inputs(agent, "这份简历有哪些问题？")

    assert state["tool_profile"] == "read_only"
    assert [tool.name for tool in pi_context.tools] == []


def test_job_match_profile_exposes_only_match_summary_tool():
    """用于验证岗位匹配意图只暴露岗位摘要工具。"""
    agent = ResumeAgent()

    pi_context, state = _build_runtime_inputs(agent, "这个 JD 的岗位匹配度怎么样？")

    assert state["tool_profile"] == "job_match"
    assert [tool.name for tool in pi_context.tools] == ["generate_job_match_summary"]


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
async def test_confirmation_policy_confirms_rejects_and_terminates_turn():
    """用于验证确认 hook 能区分确认、拒绝和本轮终止语义。"""
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
    assert result.terminate_turn is True


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
    assert session.context_summary is not None
