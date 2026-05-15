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
