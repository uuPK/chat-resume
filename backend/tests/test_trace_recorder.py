"""用于覆盖 PiAgentRuntime trace 字段记录模块。"""

from __future__ import annotations

import sys
from pathlib import Path
from time import perf_counter

import pytest
from pi_agent_core import ToolExecutionStartEvent

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.resume.agent import ResumeAgent  # noqa: E402
from app.infra.config import settings  # noqa: E402
from app.runtime.trace_recorder import DefaultTraceRecorder  # noqa: E402


@pytest.fixture(autouse=True)
def enable_trace_logs(monkeypatch: pytest.MonkeyPatch):
    """用于在测试期间打开 agent trace 日志。"""
    monkeypatch.setattr(settings, "AGENT_TRACE_LOG_ENABLED", True)
    monkeypatch.setattr(settings, "AGENT_TRACE_CHUNK_LOG_ENABLED", True)


def test_trace_recorder_records_run_start_fields(caplog: pytest.LogCaptureFixture):
    """用于验证 run start trace 字段由独立 recorder 生成。"""
    agent = ResumeAgent()
    recorder = DefaultTraceRecorder(chat_model_name=lambda: "test-model")

    with caplog.at_level("INFO", logger="app.runtime.pi_agent_runtime"):
        recorder.run_started(
            agent.definition,
            "run_1",
            "stream",
            "  优化一下\n这份简历  ",
            [{"role": "user", "content": "之前的问题"}],
        )

    record = caplog.records[0]
    assert record.getMessage() == "agent.trace.run.started"
    assert getattr(record, "agent_trace") is True
    assert getattr(record, "run_id") == "run_1"
    assert getattr(record, "agent_name") == "resume_agent"
    assert getattr(record, "mode") == "stream"
    assert getattr(record, "user_message_preview") == "优化一下 这份简历"
    assert getattr(record, "history_count") == 1
    assert "update_bullet" in getattr(record, "tool_names")


def test_trace_recorder_records_tool_executed_summary(caplog: pytest.LogCaptureFixture):
    """用于验证 tool executed trace 字段包含安全摘要而非原始结果。"""
    agent = ResumeAgent()
    recorder = DefaultTraceRecorder(chat_model_name=lambda: "test-model")
    tool_result = {
        "tool_name": "修改要点",
        "display_message": "已更新工作经历中的一条 bullet",
        "result": {
            "success": True,
            "diff_summary": "补充业务规模",
            "diff_items": [{"id": "hl_1"}],
        },
    }

    with caplog.at_level("INFO", logger="app.runtime.pi_agent_runtime"):
        recorder.tool_executed(
            agent.definition,
            "run_1",
            "call_1",
            "update_bullet",
            tool_result,
            perf_counter(),
        )

    record = caplog.records[0]
    assert record.getMessage() == "agent.trace.tool.executed"
    assert getattr(record, "tool_display_name") == "修改要点"
    assert getattr(record, "result_success") is True
    assert getattr(record, "result_summary") == {
        "keys": ["diff_items", "diff_summary", "success"],
        "success": True,
        "diff_summary": "补充业务规模",
        "diff_item_count": 1,
    }
    assert getattr(record, "latency_ms") >= 0


def test_trace_recorder_deduplicates_unexpected_tool_calls(
    caplog: pytest.LogCaptureFixture,
):
    """用于验证 unexpected tool call trace 由 recorder 维护去重状态。"""
    agent = ResumeAgent()
    recorder = DefaultTraceRecorder(chat_model_name=lambda: "test-model")
    state = {"tool_profile": "read_only", "tool_names": ["generate_job_match_summary"]}
    event = ToolExecutionStartEvent(
        tool_call_id="call_1",
        tool_name="update_bullet",
        args={},
    )

    with caplog.at_level("INFO", logger="app.runtime.pi_agent_runtime"):
        recorder.tool_call_detected(agent.definition, "run_1", event, state)
        recorder.tool_call_detected(agent.definition, "run_1", event, state)

    records = [
        record
        for record in caplog.records
        if record.getMessage() == "agent.trace.reasoning.unexpected_tool_call"
    ]
    assert len(records) == 1
    assert getattr(records[0], "tool_name") == "update_bullet"
    assert getattr(records[0], "tool_profile") == "read_only"
    assert getattr(records[0], "allowed_tool_names") == ["generate_job_match_summary"]
