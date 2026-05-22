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
    AgentContext,
    AssistantMessage,
    SimpleStreamOptions,
    StreamDoneEvent,
    StreamStartEvent,
    StreamTextDeltaEvent,
    StreamTextEndEvent,
    StreamTextStartEvent,
    StreamToolCallEndEvent,
    StreamToolCallStartEvent,
    TextContent,
    ToolCall,
    ToolExecutionStartEvent,
    ToolResultMessage,
    UserMessage,
)
from pi_agent_core.types import Model, StreamResult

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.resume.agent import ResumeAgent  # noqa: E402
from app.agents.resume.agent_loop import ResumeAgentLoop  # noqa: E402
from app.agents.resume.tool_execution import ResumeToolExecutionStage  # noqa: E402
from app.runtime import pi_agent_runtime  # noqa: E402
from app.runtime.message_conversion import convert_resume_messages_to_llm  # noqa: E402
from app.runtime.openrouter_adapter import build_openrouter_config  # noqa: E402
from app.runtime.resume_agent_session import (  # noqa: E402
    ResumeAgentSession,
    maybe_compact_resume_context,
)
from app.runtime.tool_confirmation import ToolConfirmationPolicy  # noqa: E402

RESUME_EDIT_TOOL_NAMES = {
    "update_summary",
    "update_profile",
    "upsert_job_application",
    "update_item_fields",
    "update_skills",
    "add_resume_item",
    "remove_resume_item",
    "update_overview",
    "update_bullet",
    "add_bullet",
    "remove_bullet",
    "generate_job_match_summary",
    "read_memory",
    "update_memory",
}


class FakeLoopStream:
    """用于给独立 ResumeAgentLoop 提供确定性模型事件。"""

    def __init__(self, messages: list[AssistantMessage]):
        """用于保存模型消息序列。"""
        self.messages = list(messages)
        self.contexts: list[AgentContext] = []
        self.options: list[SimpleStreamOptions] = []
        self.calls = 0

    async def __call__(
        self,
        model: Model,
        context: AgentContext,
        options: SimpleStreamOptions,
    ) -> StreamResult:
        """用于返回 pi-agent-core stream result。"""
        del model
        self.contexts.append(context)
        self.options.append(options)
        message = self.messages[self.calls]
        self.calls += 1
        events = self._events_for(message)

        async def events_iter():
            """用于按顺序返回预设流事件。"""
            for event in events:
                yield event

        async def result():
            """用于返回当前完整 assistant message。"""
            return message

        return {"events": events_iter(), "result": result}

    @staticmethod
    def _events_for(message: AssistantMessage) -> list[Any]:
        """用于把完整 assistant message 转换成测试流事件。"""
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
            if isinstance(block, ToolCall):
                events.extend(
                    [
                        StreamToolCallStartEvent(
                            content_index=index,
                            partial=message,
                        ),
                        StreamToolCallEndEvent(
                            content_index=index,
                            tool_call=block,
                            partial=message,
                        ),
                    ]
                )
        events.append(StreamDoneEvent(reason=message.stop_reason, message=message))
        return events


def fake_loop_text(text: str) -> AssistantMessage:
    """用于构造测试文本 assistant message。"""
    return AssistantMessage(content=[TextContent(text=text)], stop_reason="stop")


def fake_loop_tool_call(
    *,
    name: str,
    args: dict[str, Any],
    call_id: str,
) -> AssistantMessage:
    """用于构造测试工具调用 assistant message。"""
    return AssistantMessage(
        content=[ToolCall(id=call_id, name=name, arguments=args)],
        stop_reason="toolUse",
    )


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
    assert {tool.name for tool in pi_context.tools} == RESUME_EDIT_TOOL_NAMES


def test_system_prompt_does_not_mirror_active_tools():
    """用于验证系统提示词不再镜像实际暴露给模型的工具。"""
    agent = ResumeAgent()

    pi_context, state = _build_runtime_inputs(agent, "优化项目经历")

    assert "## 可用工具" not in pi_context.system_prompt
    assert "update_bullet" not in pi_context.system_prompt
    assert "generate_job_match_summary" not in pi_context.system_prompt
    assert set(state["tool_names"]) == RESUME_EDIT_TOOL_NAMES


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

    assert [tool.name for tool in pi_context.tools] == [
        "generate_job_match_summary",
        "read_memory",
    ]
    assert "generate_job_match_summary" not in pi_context.system_prompt
    assert "update_bullet" not in pi_context.system_prompt


def test_system_prompt_resume_json_hides_technologies_compat_fields():
    """用于验证提示词中的简历 JSON 不暴露兼容用 technologies 字段。"""
    agent = ResumeAgent()
    state = agent.runtime._new_stream_state()
    context = {
        "resume_content": {
            "work_experience": [
                {
                    "id": "work_1",
                    "company": "某科技公司",
                    "technologies": ["Python"],
                }
            ],
            "projects": [
                {
                    "id": "proj_1",
                    "name": "Deep Research Agent",
                    "technologies": ["LangChain"],
                }
            ],
        }
    }

    pi_context, _prompts, _config = agent.runtime._build_loop_inputs(
        agent=agent.definition,
        user_message="补充 Python 技术栈",
        context=context,
        conversation_history=[],
        run_id="run_test",
        confirmation_queue=None,
        event_queue=None,
        event_callback=None,
        executed_tools=[],
        stream_state=state,
    )

    assert "technologies" not in pi_context.system_prompt
    assert "Deep Research Agent" in pi_context.system_prompt


def test_job_match_message_still_exposes_resume_tools_for_model_choice():
    """用于验证岗位匹配消息不再由后端收窄工具集。"""
    agent = ResumeAgent()

    pi_context, state = _build_runtime_inputs(agent, "这个 JD 的岗位匹配度怎么样？")

    assert state["tool_profile"] == "resume_edit"
    assert {tool.name for tool in pi_context.tools} == RESUME_EDIT_TOOL_NAMES


def test_llm_request_event_records_profile_counts_and_prompt_size():
    """用于验证 LLM 请求日志字段包含 profile、工具数量和 prompt 信息。"""
    agent = ResumeAgent()
    pi_context, state = _build_runtime_inputs(agent, "优化项目经历")

    event = agent.runtime._llm_request_event(agent.definition, pi_context, [], state)

    assert event["tool_profile"] == "resume_edit"
    assert event["tool_count"] == len(RESUME_EDIT_TOOL_NAMES)
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


@pytest.mark.asyncio
async def test_resume_tool_execution_stage_runs_confirmed_tool_independently():
    """用于验证工具执行确认阶段可以脱离 PiAgentRuntime 单独测试。"""
    agent = ResumeAgent()
    stage = ResumeToolExecutionStage()
    resume = {
        "work_experience": [
            {
                "id": "work_1",
                "company": "某科技公司",
                "position": "Python 开发工程师",
                "highlights": [{"id": "hl_1", "text": "维护多个后台服务"}],
            }
        ]
    }
    confirmation_queue: asyncio.Queue[bool] = asyncio.Queue()
    confirmation_queue.put_nowait(True)
    event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    stream_state = {
        "visible_tool_call_ids": set(),
        "confirmed_diff_items": [],
        "confirmation_wait_ms": 0.0,
        "chunk_index": 0,
        "response_parts": [],
    }
    executed_tools: list[dict[str, Any]] = []

    result = await stage.execute_tool_result(
        agent=agent.definition,
        run_id="run_test",
        call_id="call_stage_1",
        tool_name="update_bullet",
        tool_input={
            "section": "work_experience",
            "item_id": "work_1",
            "bullet_id": "hl_1",
            "text": "维护多个后台服务，支撑日活 10 万用户",
            "reason": "补充业务规模",
        },
        context={"resume_content": resume, "allowed_sections": {"work_experience"}},
        confirmation_queue=confirmation_queue,
        event_queue=event_queue,
        event_callback=None,
        executed_tools=executed_tools,
        stream_state=stream_state,
    )

    events: list[dict[str, Any]] = []
    while not event_queue.empty():
        events.append(event_queue.get_nowait())

    assert "支撑日活 10 万用户" in str(result.details)
    assert resume["work_experience"][0]["highlights"][0]["text"] == (
        "维护多个后台服务，支撑日活 10 万用户"
    )
    assert any(event.get("tool_pending") for event in events)
    assert any(event.get("tool_confirmed") for event in events)
    assert executed_tools[0]["success"] is True
    assert stream_state["confirmed_diff_items"]


@pytest.mark.asyncio
async def test_resume_agent_loop_runs_react_turns_independently():
    """用于验证 ReAct loop 可以脱离 PiAgentRuntime 单独测试。"""
    agent = ResumeAgent()
    stream = FakeLoopStream(
        [
            fake_loop_tool_call(
                name="update_bullet",
                args={
                    "section": "work_experience",
                    "item_id": "work_1",
                    "bullet_id": "hl_1",
                    "text": "维护多个后台服务，支撑日活 10 万用户",
                    "reason": "补充业务规模",
                },
                call_id="call_loop_1",
            ),
            fake_loop_text("已完成优化。"),
        ]
    )
    stage = ResumeToolExecutionStage()
    loop = ResumeAgentLoop(stream_fn=stream, tool_stage=stage)
    resume = {
        "work_experience": [
            {
                "id": "work_1",
                "company": "某科技公司",
                "position": "Python 开发工程师",
                "highlights": [{"id": "hl_1", "text": "维护多个后台服务"}],
            }
        ]
    }
    state = agent.runtime._new_stream_state()
    context = {"resume_content": resume, "allowed_sections": {"work_experience"}}
    pi_context, prompts, config = agent.runtime._build_loop_inputs(
        agent=agent.definition,
        user_message="优化这段工作经历",
        context=context,
        conversation_history=[],
        run_id="run_loop_test",
        confirmation_queue=None,
        event_queue=None,
        event_callback=None,
        executed_tools=[],
        stream_state=state,
    )
    confirmation_queue: asyncio.Queue[bool] = asyncio.Queue()
    confirmation_queue.put_nowait(True)
    event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    executed_tools: list[dict[str, Any]] = []

    await loop.run(
        agent=agent.definition,
        run_id="run_loop_test",
        pi_context=pi_context,
        prompts=prompts,
        config=config,
        context=context,
        confirmation_queue=confirmation_queue,
        event_queue=event_queue,
        event_callback=None,
        state=state,
        executed_tools=executed_tools,
        model_name="test-model",
    )

    events: list[dict[str, Any]] = []
    while not event_queue.empty():
        events.append(event_queue.get_nowait())

    assert stream.calls == 2
    assert any(event.get("event_type") == "llm_request" for event in events)
    assert any(event.get("tool_pending") for event in events)
    assert any(event.get("tool_confirmed") for event in events)
    assert any(event.get("content") == "已完成优化。" for event in events)
    assert resume["work_experience"][0]["highlights"][0]["text"] == (
        "维护多个后台服务，支撑日活 10 万用户"
    )


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
