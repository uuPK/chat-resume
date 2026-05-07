"""火山引擎端到端实时语音大模型服务。

负责构建二进制协议帧，通过 WebSocket 代理前端和火山引擎之间的实时语音对话。
"""

from __future__ import annotations

import json
import logging
import math
import struct
import uuid
from typing import Any, AsyncIterator, Dict, Optional

import websockets

from app.infra.config import settings

logger = logging.getLogger(__name__)

# ── 协议常量 ──────────────────────────────────────────────

PROTOCOL_VERSION = 0b0001

# message_type
CLIENT_FULL_REQUEST = 0b0001
CLIENT_AUDIO_ONLY_REQUEST = 0b0010
SERVER_FULL_RESPONSE = 0b1001
SERVER_AUDIO_ONLY_RESPONSE = 0b1011
SERVER_ERROR_RESPONSE = 0b1111

# message_type_specific_flags
NO_SEQUENCE = 0b0000
MSG_WITH_EVENT = 0b0100

# serialization_method
NO_SERIALIZATION = 0b0000
JSON_SERIALIZATION = 0b0001

# compression
NO_COMPRESSION = 0b0000
GZIP_COMPRESSION = 0b0001

# 客户端 → 服务器事件
EVENT_START_CONNECTION = 1
EVENT_FINISH_CONNECTION = 2
EVENT_START_SESSION = 100
EVENT_FINISH_SESSION = 102
EVENT_SEND_AUDIO = 200

# 服务器 → 客户端事件
EVENT_CONNECTION_STARTED = 50
EVENT_CONNECTION_FAILED = 51
EVENT_CONNECTION_FINISHED = 52
EVENT_SESSION_STARTED = 150
EVENT_SESSION_FINISHED = 152
EVENT_SESSION_FAILED = 153
EVENT_TTS_SENTENCE_START = 350
EVENT_TTS_SENTENCE_END = 351
EVENT_TTS_RESPONSE = 352
EVENT_TTS_ENDED = 359
EVENT_ASR_INFO = 450
EVENT_ASR_RESPONSE = 451
EVENT_ASR_ENDED = 459
EVENT_CHAT_RESPONSE = 550
EVENT_CHAT_ENDED = 559

# 音频参数
SEND_SAMPLE_RATE = 16000
SEND_CHUNK_FRAMES = 1600  # 100ms @ 16kHz
RECV_SAMPLE_RATE = 24000


class VolcengineConfigurationError(RuntimeError):
    """用于提示火山引擎必要环境变量尚未配置。"""


# ── 二进制帧构建 ──────────────────────────────────────────


def _build_header(
    *,
    message_type: int = CLIENT_FULL_REQUEST,
    message_type_specific_flags: int = MSG_WITH_EVENT,
    serial_method: int = JSON_SERIALIZATION,
    compression_type: int = NO_COMPRESSION,
) -> bytes:
    header_size = 1
    return bytes([
        (PROTOCOL_VERSION << 4) | header_size,
        (message_type << 4) | message_type_specific_flags,
        (serial_method << 4) | compression_type,
        0x00,
    ])


def _build_json_frame(event_id: int, payload: Dict[str, Any]) -> bytes:
    header = _build_header()
    payload_bytes = json.dumps(payload).encode("utf-8")
    return (
        header
        + struct.pack(">I", event_id)
        + struct.pack(">I", len(payload_bytes))
        + payload_bytes
    )


def _build_session_json_frame(
    event_id: int, session_id: str, payload: Dict[str, Any]
) -> bytes:
    header = _build_header()
    sid_bytes = session_id.encode("utf-8")
    payload_bytes = json.dumps(payload).encode("utf-8")
    return (
        header
        + struct.pack(">I", event_id)
        + struct.pack(">I", len(sid_bytes))
        + sid_bytes
        + struct.pack(">I", len(payload_bytes))
        + payload_bytes
    )


def _build_audio_frame(session_id: str, pcm_bytes: bytes) -> bytes:
    header = _build_header(
        message_type=CLIENT_AUDIO_ONLY_REQUEST,
        message_type_specific_flags=MSG_WITH_EVENT,
        serial_method=NO_SERIALIZATION,
        compression_type=NO_COMPRESSION,
    )
    sid_bytes = session_id.encode("utf-8")
    return (
        header
        + struct.pack(">I", EVENT_SEND_AUDIO)
        + struct.pack(">I", len(sid_bytes))
        + sid_bytes
        + struct.pack(">I", len(pcm_bytes))
        + pcm_bytes
    )


def _build_start_connection() -> bytes:
    return _build_json_frame(EVENT_START_CONNECTION, {})


def _build_finish_connection() -> bytes:
    return _build_json_frame(EVENT_FINISH_CONNECTION, {})


def _build_start_session(
    session_id: str,
    *,
    bot_name: str = "面试官",
    system_role: str = "",
    speaking_style: str = "",
    speaker_id: str = "",
    model: str = "O",
    input_mod: str = "keep_alive",
) -> bytes:
    dialog: Dict[str, Any] = {
        "bot_name": bot_name,
        "extra": {
            "input_mod": input_mod,
            "model": model,
        },
    }
    if system_role:
        dialog["system_role"] = system_role[:4000]
    if speaking_style:
        dialog["speaking_style"] = speaking_style
    tts: Dict[str, Any] = {
        "audio_config": {
            "format": "pcm_s16le",
            "sample_rate": RECV_SAMPLE_RATE,
            "channel": 1,
            "bits": 16,
        },
    }
    if speaker_id:
        tts["speaker"] = speaker_id
    return _build_session_json_frame(
        EVENT_START_SESSION,
        session_id,
        {
            "dialog": dialog,
            "asr": {
                "language": "zh-CN",
            },
            "tts": tts,
        },
    )


def _build_finish_session(session_id: str) -> bytes:
    return _build_session_json_frame(EVENT_FINISH_SESSION, session_id, {})


def _describe_pcm16(pcm_bytes: bytes) -> Dict[str, float | int]:
    """Return small PCM diagnostics so we can tell silence from speech."""
    if len(pcm_bytes) < 2:
        return {"samples": 0, "rms": 0.0, "peak": 0}

    sample_count = len(pcm_bytes) // 2
    total_square = 0
    peak = 0
    for (sample,) in struct.iter_unpack("<h", pcm_bytes[: sample_count * 2]):
        abs_sample = abs(sample)
        peak = max(peak, abs_sample)
        total_square += sample * sample

    rms = math.sqrt(total_square / sample_count) if sample_count else 0.0
    return {
        "samples": sample_count,
        "rms": round(rms, 2),
        "peak": peak,
    }


# ── 二进制帧解析 ──────────────────────────────────────────


def _parse_server_message(data: bytes) -> Optional[Dict[str, Any]]:
    """解析服务器发来的二进制消息，返回结构化事件。"""
    if len(data) < 4:
        return None

    header_size = (data[0] & 0x0F) * 4
    message_type = data[1] >> 4
    message_type_flags = data[1] & 0x0F
    serialization = data[2] >> 4
    compression = data[2] & 0x0F

    offset = header_size

    event_id = 0
    if message_type_flags & 0x04:  # MSG_WITH_EVENT
        if offset + 4 > len(data):
            return None
        event_id = struct.unpack(">I", data[offset : offset + 4])[0]
        offset += 4

    # session_id / connect_id
    session_id = ""
    if _event_has_session_id(event_id) and offset + 4 <= len(data):
        sid_len = struct.unpack(">I", data[offset : offset + 4])[0]
        offset += 4
        if offset + sid_len <= len(data):
            session_id = data[offset : offset + sid_len].decode("utf-8", errors="replace")
            offset += sid_len
    elif _event_has_connect_id(event_id) and offset + 4 <= len(data):
        connect_id_len = struct.unpack(">I", data[offset : offset + 4])[0]
        offset += 4
        if offset + connect_id_len <= len(data):
            session_id = data[offset : offset + connect_id_len].decode("utf-8", errors="replace")
            offset += connect_id_len

    # payload
    payload_data = b""
    if offset + 4 <= len(data):
        payload_len = struct.unpack(">I", data[offset : offset + 4])[0]
        offset += 4
        if offset + payload_len <= len(data):
            payload_data = data[offset : offset + payload_len]

    # 解码
    if event_id == EVENT_TTS_RESPONSE or message_type == SERVER_AUDIO_ONLY_RESPONSE:
        # TTS 音频数据是原始 PCM，不需要解压
        return {"event": event_id, "session_id": session_id, "audio": payload_data}

    if compression == GZIP_COMPRESSION and payload_data:
        import gzip

        payload_data = gzip.decompress(payload_data)

    if serialization == JSON_SERIALIZATION and payload_data:
        try:
            return {
                "event": event_id,
                "session_id": session_id,
                "data": json.loads(payload_data.decode("utf-8")),
            }
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

    return {"event": event_id, "session_id": session_id, "raw": payload_data}


def _event_has_session_id(event_id: int) -> bool:
    return event_id not in {
        EVENT_START_CONNECTION,
        EVENT_FINISH_CONNECTION,
        EVENT_CONNECTION_STARTED,
        EVENT_CONNECTION_FAILED,
        EVENT_CONNECTION_FINISHED,
    }


def _event_has_connect_id(event_id: int) -> bool:
    return event_id in {
        EVENT_CONNECTION_STARTED,
        EVENT_CONNECTION_FAILED,
        EVENT_CONNECTION_FINISHED,
    }


def _extract_realtime_text(data: Dict[str, Any]) -> str:
    """Normalize text fields used by Volcengine realtime events."""
    for key in ("content", "text"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value

    for nested_key in ("asr_info", "tts_info"):
        nested = data.get(nested_key)
        if isinstance(nested, dict):
            for key in ("content", "text"):
                value = nested.get(key)
                if isinstance(value, str) and value:
                    return value

    results = data.get("results")
    if isinstance(results, list):
        texts = [
            item.get("text", "")
            for item in results
            if isinstance(item, dict)
        ]
        return "".join(texts)

    return ""


def _extract_is_final(data: Dict[str, Any]) -> bool:
    if isinstance(data.get("is_final"), bool):
        return data["is_final"]
    for nested_key in ("asr_info", "tts_info"):
        nested = data.get(nested_key)
        if isinstance(nested, dict) and isinstance(nested.get("is_final"), bool):
            return nested["is_final"]
    return False


# ── 服务类 ────────────────────────────────────────────────


class VolcengineVoiceService:
    """用于管理火山引擎端到端实时语音对话的 WebSocket 连接。"""

    # 火山引擎要求的固定 App Key，见文档 2.1 节
    _FIXED_APP_KEY = "PlgvMymc7f3tQnJ6"

    def __init__(self) -> None:
        self.ws_url = settings.VOLCENGINE_DIALOGUE_WS_URL
        self.app_id = settings.VOLCENGINE_DIALOGUE_APP_ID
        self.access_key = settings.VOLCENGINE_DIALOGUE_ACCESS_KEY
        self.resource_id = settings.VOLCENGINE_DIALOGUE_RESOURCE_ID
        self.speaker_id = settings.VOLCENGINE_DIALOGUE_SPEAKER_ID.strip()

    def is_configured(self) -> bool:
        return bool(self.app_id and self.access_key)

    def _ensure_configured(self) -> None:
        if not self.is_configured():
            raise VolcengineConfigurationError(
                "Volcengine dialogue is not configured. "
                "Set VOLCENGINE_DIALOGUE_APP_ID and VOLCENGINE_DIALOGUE_ACCESS_KEY."
            )

    def build_headers(self, connect_id: str) -> Dict[str, str]:
        self._ensure_configured()
        return {
            "X-Api-App-Key": self._FIXED_APP_KEY,
            "X-Api-App-ID": self.app_id,
            "X-Api-Access-Key": self.access_key,
            "X-Api-Resource-Id": self.resource_id,
            "X-Api-Connect-Id": connect_id,
        }

    async def proxy_session(
        self,
        *,
        client_ws: Any,
        system_role: str = "",
        bot_name: str = "面试官",
    ) -> None:
        """在前端 WebSocket 和火山引擎之间双向代理音视数据。

        client_ws: Starlette/FastAPI WebSocket 对象（已 accept）。
        """
        self._ensure_configured()

        session_id = str(uuid.uuid4())
        connect_id = str(uuid.uuid4())

        headers = self.build_headers(connect_id)

        try:
            ws_ctx = websockets.connect(
                self.ws_url,
                extra_headers=headers,
                max_size=None,
            )
            volc_ws = await ws_ctx.__aenter__()
        except Exception as conn_exc:
            logger.error(
                "Volcengine WS connect failed [%s.%s]: %s",
                type(conn_exc).__module__,
                type(conn_exc).__qualname__,
                conn_exc,
            )
            try:
                import httpx
                async with httpx.AsyncClient() as client:
                    probe_resp = await client.get(
                        self.ws_url.replace("wss://", "https://"),
                        headers=headers,
                    )
                    logger.error(
                        "Volcengine probe: status=%s body=%s",
                        probe_resp.status_code,
                        probe_resp.text[:500],
                    )
            except Exception as probe_exc:
                logger.error("Volcengine probe also failed: %s", probe_exc)
            raise

        try:
            # 1) Start connection
            await volc_ws.send(_build_start_connection())
            resp = await volc_ws.recv()
            parsed = _parse_server_message(resp)
            logger.info("Volcengine start_connection response: %s", parsed)
            if not parsed or parsed.get("event") != EVENT_CONNECTION_STARTED:
                logger.error("Volcengine connection failed: %s", parsed)
                await client_ws.send_json({"type": "error", "message": "连接火山引擎失败"})
                return

            # 2) Start session
            await volc_ws.send(_build_start_session(
                session_id,
                bot_name=bot_name,
                system_role=system_role,
                speaker_id=self.speaker_id,
            ))
            resp = await volc_ws.recv()
            parsed = _parse_server_message(resp)
            logger.info("Volcengine start_session response: %s", parsed)
            if not parsed or parsed.get("event") != EVENT_SESSION_STARTED:
                logger.error("Volcengine session failed: %s", parsed)
                await client_ws.send_json({"type": "error", "message": "启动语音会话失败"})
                await volc_ws.send(_build_finish_connection())
                return

            await client_ws.send_json({"type": "ready", "session_id": session_id})

            # 3) 双向转发
            import asyncio

            closing = asyncio.Event()

            async def forward_to_volcengine():
                chunk_count = 0
                voiced_chunk_count = 0
                try:
                    while not closing.is_set():
                        msg = await client_ws.receive()
                        if msg["type"] == "websocket.disconnect":
                            break
                        if msg["type"] == "websocket.receive":
                            if "bytes" in msg and msg["bytes"]:
                                pcm_stats = _describe_pcm16(msg["bytes"])
                                if pcm_stats["peak"] >= 800:
                                    voiced_chunk_count += 1
                                await volc_ws.send(
                                    _build_audio_frame(session_id, msg["bytes"])
                                )
                                chunk_count += 1
                                if chunk_count <= 3 or chunk_count % 100 == 0:
                                    logger.info(
                                        (
                                            "Sent audio chunk #%d (%d bytes) to Volcengine "
                                            "pcm=%s voiced_chunks=%d"
                                        ),
                                        chunk_count,
                                        len(msg["bytes"]),
                                        pcm_stats,
                                        voiced_chunk_count,
                                    )
                            elif "text" in msg and msg["text"]:
                                try:
                                    ctrl = json.loads(msg["text"])
                                    if ctrl.get("type") == "end":
                                        break
                                except json.JSONDecodeError:
                                    pass
                except Exception as exc:
                    logger.warning("forward_to_volcengine error: %s", exc)
                finally:
                    logger.info(
                        "Upstream done, sent %d audio chunks total, voiced_chunks=%d",
                        chunk_count,
                        voiced_chunk_count,
                    )
                    closing.set()
                    try:
                        await volc_ws.send(_build_finish_session(session_id))
                        await asyncio.sleep(0.1)
                        await volc_ws.send(_build_finish_connection())
                    except Exception:
                        pass

            async def forward_to_client():
                msg_count = 0
                try:
                    async for msg in volc_ws:
                        if closing.is_set():
                            return
                        msg_count += 1
                        if isinstance(msg, bytes):
                            parsed = _parse_server_message(msg)
                            if not parsed:
                                continue

                            event = parsed.get("event")

                            if msg_count <= 10:
                                logger.info(
                                    "Volcengine msg #%d: event=%s data=%s raw_bytes=%d audio_bytes=%d",
                                    msg_count,
                                    event,
                                    parsed.get("data", {}),
                                    len(parsed.get("raw", b"") or b""),
                                    len(parsed.get("audio", b"") or b""),
                                )

                            if event == EVENT_TTS_RESPONSE:
                                audio = parsed.get("audio", b"")
                                if audio:
                                    await client_ws.send_bytes(audio)
                            elif event in (
                                EVENT_ASR_RESPONSE,
                                EVENT_ASR_INFO,
                                EVENT_ASR_ENDED,
                                EVENT_CHAT_RESPONSE,
                                EVENT_CHAT_ENDED,
                            ):
                                event_data = parsed.get("data", {})
                                await client_ws.send_json({
                                    "type": "event",
                                    "event": event,
                                    "data": event_data,
                                    "text": _extract_realtime_text(event_data),
                                    "is_final": _extract_is_final(event_data)
                                    or event in (EVENT_ASR_ENDED, EVENT_CHAT_ENDED),
                                    "turn_id": event_data.get("reqid")
                                    or event_data.get("trace_id")
                                    or f"{event}-{msg_count}",
                                })
                            elif event in (
                                EVENT_SESSION_FINISHED,
                                EVENT_CONNECTION_FINISHED,
                                EVENT_SESSION_FAILED,
                            ):
                                await client_ws.send_json({
                                    "type": "event",
                                    "event": event,
                                })
                                return
                except Exception as exc:
                    logger.warning("forward_to_client error: %s", exc)
                finally:
                    logger.info("Downstream done, received %d messages total", msg_count)
                    closing.set()

            await asyncio.gather(
                forward_to_volcengine(),
                forward_to_client(),
                return_exceptions=True,
            )
        finally:
            try:
                await ws_ctx.__aexit__(None, None, None)
            except Exception:
                pass
