"""测试面试官开场白功能。

覆盖范围：
1. _build_say_hello_frame 生成正确的 event 300 帧
2. proxy_session 在 greeting 非空时发送 SayHello 帧给 Volcengine
3. proxy_session 在 greeting 为空时不发送 SayHello 帧
4. _build_greeting 中英文输出正确
5. _build_greeting 无 title/company 时使用通用文案
"""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.digital_human.volcengine_service import (
    EVENT_SAY_HELLO,
    EVENT_START_SESSION,
    _build_say_hello_frame,
    _build_start_session,
)
from app.entrypoints.http.digital_human import (
    _build_greeting,
    _build_interview_context,
    _build_volcengine_system_role,
)


# ── 工具：解码 session 类事件帧 ──────────────────────────────────────────────

def _decode_session_frame(frame: bytes) -> tuple[int, dict]:
    """返回 (event_id, payload_dict)。"""
    offset = 4  # skip header
    event_id = struct.unpack(">I", frame[offset: offset + 4])[0]
    offset += 4
    sid_len = struct.unpack(">I", frame[offset: offset + 4])[0]
    offset += 4 + sid_len
    payload_len = struct.unpack(">I", frame[offset: offset + 4])[0]
    offset += 4
    payload = json.loads(frame[offset: offset + payload_len].decode("utf-8"))
    return event_id, payload


# ── 1. _build_say_hello_frame ────────────────────────────────────────────────

def test_build_say_hello_frame_event_id():
    """用于验证buildsayhelloframe事件id。"""
    frame = _build_say_hello_frame("sess-001", "你好，面试开始！")
    event_id, payload = _decode_session_frame(frame)
    assert event_id == EVENT_SAY_HELLO


def test_build_say_hello_frame_content():
    """用于验证buildsayhelloframecontent。"""
    frame = _build_say_hello_frame("sess-002", "欢迎来到模拟面试。")
    _, payload = _decode_session_frame(frame)
    assert payload["content"] == "欢迎来到模拟面试。"


def test_build_start_session_no_prologue_field():
    """StartSession 帧不应包含 prologue 字段（官方文档无此参数）。"""
    frame = _build_start_session("sess-003", system_role="你是面试官")
    event_id, payload = _decode_session_frame(frame)
    assert event_id == EVENT_START_SESSION
    assert "prologue" not in payload.get("dialog", {})


# ── 2. _build_greeting ───────────────────────────────────────────────────────

def test_build_greeting_chinese_with_context():
    """用于验证buildgreetingchinesewith上下文。"""
    text = _build_greeting(target_title="后端工程师", target_company="字节跳动", language="zh-CN")
    assert "后端工程师" in text
    assert "字节跳动" in text


def test_build_greeting_english_with_context():
    """用于验证buildgreetingenglishwith上下文。"""
    text = _build_greeting(target_title="Backend Engineer", target_company="ByteDance", language="en")
    assert "Backend Engineer" in text
    assert "ByteDance" in text


def test_build_greeting_chinese_no_context():
    """title/company 为空时使用通用文案，不出现占位符字样。"""
    text = _build_greeting(target_title="", target_company="", language="zh-CN")
    assert "目标岗位" not in text
    assert "目标公司" not in text
    assert len(text) > 5




def test_build_volcengine_system_role_uses_interviewer_prompt():
    """豆包端到端语音 system_role 应从 interviewer_agent 提示词渲染。"""
    text = _build_volcengine_system_role(
        target_title="后端工程师",
        target_company="字节跳动",
        language="zh-CN",
        difficulty="hard",
        jd_text="负责高并发服务",
        resume_text="候选人姓名：张三",
        interview_history="面试官：请介绍项目",
    )

    assert "中文模拟面试官" in text
    assert "后端工程师" in text
    assert "候选人简历信息：\n候选人姓名：张三" in text
    assert "岗位 JD 信息：\n负责高并发服务" in text
    assert "不要重复开场白" in text


def test_build_interview_context_uses_same_prompt_file():
    """Tavus 会话上下文应复用 interviewer_agent 提示词。"""
    text = _build_interview_context(
        target_title="Backend Engineer",
        target_company="ByteDance",
        language="en-US",
        difficulty="medium",
        jd_text="Own backend systems",
    )

    assert "professional mock interviewer" in text
    assert "Backend Engineer" in text
    assert "Job description context:\nOwn backend systems" in text
# ── helpers ──────────────────────────────────────────────────────────────────

import struct as _struct


def _make_server_frame(event_id: int, body: bytes) -> bytes:
    """用于处理makeserverframe。"""
    from app.services.digital_human.volcengine_service import (
        MSG_WITH_EVENT, JSON_SERIALIZATION, NO_COMPRESSION,
        PROTOCOL_VERSION, SERVER_FULL_RESPONSE,
    )
    header = bytes([
        (PROTOCOL_VERSION << 4) | 1,
        (SERVER_FULL_RESPONSE << 4) | MSG_WITH_EVENT,
        (JSON_SERIALIZATION << 4) | NO_COMPRESSION,
        0x00,
    ])
    id_bytes = b"test-id"
    return (
        header
        + _struct.pack(">I", event_id)
        + _struct.pack(">I", len(id_bytes)) + id_bytes
        + _struct.pack(">I", len(body)) + body
    )


async def _run_proxy(monkeypatch, greeting: str):
    """用于运行proxy。"""
    from app.infra.config import settings
    from app.services.digital_human.volcengine_service import (
        VolcengineVoiceService, EVENT_CONNECTION_STARTED, EVENT_SESSION_STARTED,
    )
    monkeypatch.setattr(settings, "VOLCENGINE_DIALOGUE_APP_ID", "test-app")
    monkeypatch.setattr(settings, "VOLCENGINE_DIALOGUE_ACCESS_KEY", "test-key")
    monkeypatch.setattr(settings, "VOLCENGINE_DIALOGUE_RESOURCE_ID", "test-res")
    monkeypatch.setattr(settings, "VOLCENGINE_DIALOGUE_SPEAKER_ID", "")

    captured_frames: list[bytes] = []
    client_json_calls: list[dict] = []

    recv_responses = [
        _make_server_frame(EVENT_CONNECTION_STARTED, b"{}"),
        _make_server_frame(EVENT_SESSION_STARTED, b"{}"),
    ]
    mock_volc_ws = AsyncMock()
    mock_volc_ws.recv = AsyncMock(side_effect=recv_responses)
    mock_volc_ws.__aiter__ = MagicMock(return_value=iter([]))

    async def fake_send(data):
        """用于构造send。"""
        if isinstance(data, bytes):
            captured_frames.append(data)

    mock_volc_ws.send = AsyncMock(side_effect=fake_send)
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_volc_ws)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_client_ws = AsyncMock()
    mock_client_ws.receive = AsyncMock(side_effect=[{"type": "websocket.disconnect"}])

    async def capture_json(payload):
        """用于处理capturejson。"""
        client_json_calls.append(payload)

    mock_client_ws.send_json = AsyncMock(side_effect=capture_json)

    with patch("websockets.connect", return_value=mock_ctx):
        service = VolcengineVoiceService()
        await service.proxy_session(client_ws=mock_client_ws, system_role="你是面试官", greeting=greeting)

    return captured_frames, client_json_calls


# ── 3. proxy_session SayHello ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_proxy_session_sends_say_hello_when_greeting(monkeypatch):
    """greeting 非空时，proxy_session 应发送 event 300 SayHello 给 Volcengine。"""
    greeting = "你好，欢迎来到模拟面试！"
    captured_frames, _ = await _run_proxy(monkeypatch, greeting)

    say_hello_frames = [
        f for f in captured_frames
        if len(f) >= 8 and struct.unpack(">I", f[4:8])[0] == EVENT_SAY_HELLO
    ]
    assert len(say_hello_frames) == 1, "应恰好发送 1 个 SayHello 帧"
    _, payload = _decode_session_frame(say_hello_frames[0])
    assert payload["content"] == greeting


@pytest.mark.asyncio
async def test_proxy_session_no_say_hello_when_empty_greeting(monkeypatch):
    """greeting 为空时不发送 SayHello 帧。"""
    captured_frames, _ = await _run_proxy(monkeypatch, "")
    say_hello_frames = [
        f for f in captured_frames
        if len(f) >= 8 and struct.unpack(">I", f[4:8])[0] == EVENT_SAY_HELLO
    ]
    assert len(say_hello_frames) == 0
