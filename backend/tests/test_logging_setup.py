"""用于覆盖后端日志输出目标配置。"""

from __future__ import annotations

import logging
import re

from app.infra import logging_setup
from app.infra.config import settings

_ANSI_PATTERN = re.compile(r"\x1b\[[0-9;]*m")


def test_text_logging_colors_terminal_but_not_file(tmp_path, monkeypatch, capsys):
    """用于验证终端彩色输出而日志文件保持纯文本。"""
    log_file = tmp_path / "backend.log"
    monkeypatch.setattr(settings, "LOG_FORMAT", "text")
    monkeypatch.setattr(settings, "LOG_LEVEL", "INFO")
    monkeypatch.setattr(settings, "BACKEND_LOG_FILE", str(log_file))

    logging_setup.configure_logging()
    logging.getLogger("app.main").info("app.ready")

    terminal_output = capsys.readouterr().err
    file_output = log_file.read_text(encoding="utf-8")

    assert _ANSI_PATTERN.search(terminal_output)
    assert "app.ready" in terminal_output
    assert "app.ready" in file_output
    assert not _ANSI_PATTERN.search(file_output)


def test_text_request_logs_include_client_request_id(tmp_path, monkeypatch):
    """用于验证本地文本日志可以按前端请求 ID grep。"""
    log_file = tmp_path / "backend.log"
    monkeypatch.setattr(settings, "LOG_FORMAT", "text")
    monkeypatch.setattr(settings, "LOG_LEVEL", "INFO")
    monkeypatch.setattr(settings, "BACKEND_LOG_FILE", str(log_file))

    logging_setup.configure_logging()
    logging.getLogger("app.main").info(
        "request.finished",
        extra={
            "http_method": "POST",
            "http_path": "/api/ai/chat/stream",
            "http_status": 500,
            "request_ms": 1200.0,
            "client_request_id": "ai_client_visible_123",
        },
    )

    file_output = log_file.read_text(encoding="utf-8")

    assert "request.finished POST /api/ai/chat/stream 500 1200.0ms" in file_output
    assert "client=ai_client_visible_123" in file_output


def test_text_sse_tool_event_log_includes_core_fields(tmp_path, monkeypatch):
    """用于验证 SSE 工具事件日志默认可读。"""
    log_file = tmp_path / "backend.log"
    monkeypatch.setattr(settings, "LOG_FORMAT", "text")
    monkeypatch.setattr(settings, "LOG_LEVEL", "INFO")
    monkeypatch.setattr(settings, "BACKEND_LOG_FILE", str(log_file))

    logging_setup.configure_logging()
    logging.getLogger("app.entrypoints.http.resume_agent").info(
        "resume_agent.sse.tool_event.sent",
        extra={
            "event_type": "tool_call",
            "tool_name": "update_bullet",
            "call_id": "call_123456789",
            "client_request_id": "ai_client_visible_123",
            "has_result": False,
        },
    )

    file_output = log_file.read_text(encoding="utf-8")

    assert "sse.tool_event sent" in file_output
    assert "event=tool_call" in file_output
    assert "tool=update_bullet" in file_output
    assert "call=call_123456789" in file_output
    assert "client=ai_clien" in file_output
    assert "client=ai_client_visible_123" not in file_output
