"""用于覆盖后端日志输出目标配置。"""

from __future__ import annotations

import logging
import re
import sys

from app.infra import logging_setup
from app.infra.config import settings

_ANSI_PATTERN = re.compile(r"\x1b\[[0-9;]*m")


def test_text_logging_colors_terminal_and_file(tmp_path, monkeypatch, capsys):
    """用于验证终端和日志文件都保持彩色输出。"""
    log_file = tmp_path / "backend.log"
    monkeypatch.setattr(settings, "LOG_FORMAT", "text")
    monkeypatch.setattr(settings, "LOG_LEVEL", "INFO")
    monkeypatch.setattr(settings, "BACKEND_LOG_FILE", str(log_file))
    monkeypatch.setattr(sys.stderr, "isatty", lambda: True)

    logging_setup.configure_logging()
    logging.getLogger("app.main").info("app.ready")

    terminal_output = capsys.readouterr().err
    file_output = log_file.read_text(encoding="utf-8")

    assert _ANSI_PATTERN.search(terminal_output)
    assert _ANSI_PATTERN.search(file_output)
    assert "app.ready" in terminal_output
    assert "app.ready" in file_output
    assert file_output.count("app.ready") == 1


def test_text_logging_skips_terminal_sink_when_stderr_is_pipe(
    tmp_path,
    monkeypatch,
    capsys,
):
    """用于验证非 TTY stderr 不会额外输出一份终端日志。"""
    log_file = tmp_path / "backend.log"
    monkeypatch.setattr(settings, "LOG_FORMAT", "text")
    monkeypatch.setattr(settings, "LOG_LEVEL", "INFO")
    monkeypatch.setattr(settings, "BACKEND_LOG_FILE", str(log_file))
    monkeypatch.setattr(sys.stderr, "isatty", lambda: False)

    logging_setup.configure_logging()
    logging.getLogger("app.main").info("app.ready")

    terminal_output = capsys.readouterr().err
    file_output = log_file.read_text(encoding="utf-8")

    assert terminal_output == ""
    assert file_output.count("app.ready") == 1
    assert _ANSI_PATTERN.search(file_output)
