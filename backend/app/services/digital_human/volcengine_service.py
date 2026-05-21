"""火山引擎端到端实时语音大模型服务。

负责构建二进制协议帧，通过 WebSocket 代理前端和火山引擎之间的实时语音对话。
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import math
import struct
import time
import uuid
from typing import Any, Callable, Dict, Optional

import httpx
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
EVENT_SAY_HELLO = 300        # 触发豆包说开场白，payload: {"content": "..."}

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
VOICE_PEAK_THRESHOLD = 800


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
    """用于构建头部。"""
    header_size = 1
    return bytes([
        (PROTOCOL_VERSION << 4) | header_size,
        (message_type << 4) | message_type_specific_flags,
        (serial_method << 4) | compression_type,
        0x00,
    ])


def _build_json_frame(event_id: int, payload: Dict[str, Any]) -> bytes:
    """用于构建JSON帧。"""
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
    """用于构建会话JSON帧。"""
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
    """用于构建音频帧。"""
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
    """用于构建开始连接。"""
    return _build_json_frame(EVENT_START_CONNECTION, {})


def _build_finish_connection() -> bytes:
    """用于构建结束连接。"""
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
    """用于构建开始会话。"""
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
    """用于构建结束会话。"""
    return _build_session_json_frame(EVENT_FINISH_SESSION, session_id, {})


def _build_say_hello_frame(session_id: str, content: str) -> bytes:
    """Event 300：让豆包用自己的声音说出 content 作为开场白。"""
    return _build_session_json_frame(EVENT_SAY_HELLO, session_id, {"content": content})



def _elapsed_ms(started_at: float) -> float:
    """返回从 started_at 到当前的毫秒数。"""
    return round((time.monotonic() - started_at) * 1000, 2)

def _describe_pcm16(pcm_bytes: bytes) -> Dict[str, float | int]:
    """用于描述pcm16。"""
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
            session_id = data[offset : offset + sid_len].decode(
                "utf-8",
                errors="replace",
            )
            offset += sid_len
    elif _event_has_connect_id(event_id) and offset + 4 <= len(data):
        connect_id_len = struct.unpack(">I", data[offset : offset + 4])[0]
        offset += 4
        if offset + connect_id_len <= len(data):
            session_id = data[offset : offset + connect_id_len].decode(
                "utf-8",
                errors="replace",
            )
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


def _coerce_ws_bytes(data: str | bytes) -> bytes:
    """用于转换WebSocket字节。"""
    if isinstance(data, bytes):
        return data
    return data.encode("utf-8")


def _event_has_session_id(event_id: int) -> bool:
    """用于处理事件has会话标识。"""
    return event_id not in {
        EVENT_START_CONNECTION,
        EVENT_FINISH_CONNECTION,
        EVENT_CONNECTION_STARTED,
        EVENT_CONNECTION_FAILED,
        EVENT_CONNECTION_FINISHED,
    }


def _event_has_connect_id(event_id: int) -> bool:
    """用于处理事件has连接标识。"""
    return event_id in {
        EVENT_CONNECTION_STARTED,
        EVENT_CONNECTION_FAILED,
        EVENT_CONNECTION_FINISHED,
    }


def _realtime_event_role(event_id: Any) -> str:
    """把实时文本事件映射为面试对话角色。"""
    if event_id in (EVENT_ASR_RESPONSE, EVENT_ASR_INFO, EVENT_ASR_ENDED):
        return "candidate"
    if event_id in (EVENT_CHAT_RESPONSE, EVENT_CHAT_ENDED):
        return "interviewer"
    return ""


def _realtime_text_with_pending(
    *, role: str, text: str, is_final: bool, pending_by_role: dict[str, str]
) -> str:
    """用最近一次非空增量补齐空的最终实时文本事件。"""
    if not role:
        return text
    if text:
        pending_by_role[role] = text
        return text
    if is_final:
        return pending_by_role.get(role, "")
    return ""


def _extract_realtime_text(data: Dict[str, Any]) -> str:
    """用于提取实时文本。"""
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
    """用于提取isfinal。"""
    if isinstance(data.get("is_final"), bool):
        return data["is_final"]
    for nested_key in ("asr_info", "tts_info"):
        nested = data.get(nested_key)
        if isinstance(nested, dict) and isinstance(nested.get("is_final"), bool):
            return nested["is_final"]
    return False


# ── 开场白 TTS ───────────────────────────────────────────


async def _synthesize_greeting_pcm(text: str, speaker_id: str = "") -> Optional[bytes]:
    """用火山引擎 TTS HTTP API 把开场白合成为 PCM s16le 24kHz mono 字节流。

    使用与实时对话相同的 speaker_id，确保声音一致。
    """
    tts_api_key = settings.VOLCENGINE_TTS_API_KEY
    tts_app_id  = settings.VOLCENGINE_TTS_APP_ID
    if not (tts_api_key and tts_app_id):
        logger.warning(
            "Volcengine TTS not configured: TTS_APP_ID=%r TTS_API_KEY=%s",
            tts_app_id or "(empty)",
            "set" if tts_api_key else "(empty)",
        )
        return None

    voice_type = speaker_id or "BV700_streaming"
    # 大模型语音合成用 volcano_mega；标准 TTS 用 volcano_tts
    cluster = settings.VOLCENGINE_TTS_CLUSTER or "volcano_mega"
    payload = {
        "app": {"appid": tts_app_id, "token": tts_api_key, "cluster": cluster},
        "user": {"uid": "interview-greeting"},
        "audio": {
            "voice_type": voice_type,
            "encoding": "pcm",
            "sample_rate": RECV_SAMPLE_RATE,
            "speed_ratio": 1.0,
            "volume_ratio": 1.0,
            "pitch_ratio": 1.0,
        },
        "request": {
            "reqid": str(uuid.uuid4()),
            "text": text,
            "text_type": "plain",
            "operation": "query",
        },
    }
    headers = {
        "Authorization": f"Bearer;{tts_api_key}",
        "Content-Type": "application/json",
    }
    logger.info(
        "Greeting TTS request: appid=%s cluster=%s voice=%s text_len=%d",
        tts_app_id, cluster, voice_type, len(text),
    )
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://openspeech.bytedance.com/api/v1/tts",
                json=payload,
                headers=headers,
            )
            logger.info(
                "volcengine.greeting_tts.response",
                extra={
                    "http_status": resp.status_code,
                    "content_type": resp.headers.get("content-type", ""),
                    "response_chars": len(resp.text or ""),
                },
            )
            resp.raise_for_status()
            body = resp.json()
            code = body.get("code")
            if code != 3000:
                logger.warning(
                    "volcengine.greeting_tts.error",
                    extra={"provider_code": code},
                )
                return None
            audio_b64 = body.get("data")
            if not audio_b64:
                logger.warning("Volcengine TTS: missing data field in response")
                return None
            pcm = base64.b64decode(audio_b64)
            logger.info("Greeting TTS success: %d PCM bytes", len(pcm))
            return pcm
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "volcengine.greeting_tts.http_error",
            extra={"http_status": exc.response.status_code},
        )
    except Exception as exc:
        logger.warning("Greeting TTS failed: %s", exc)
    return None


async def _synthesize_trigger_pcm_with_dialogue_creds() -> Optional[bytes]:
    """用豆包实时对话 APP 的凭证调大模型语音合成，合成 16kHz PCM 触发词。

    大模型语音合成使用 X-Api-* 头部认证，与实时对话同一套 APP 凭证。
    输出 16kHz s16le mono PCM，可直接作为音频帧发给实时对话 session。
    """
    app_id = settings.VOLCENGINE_DIALOGUE_APP_ID
    # app.token 用通用 Access Token（控制台"服务接口认证信息"里的 Access Token）
    token = settings.VOLCENGINE_ACCESS_TOKEN
    if not (app_id and token):
        logger.warning(
            "Trigger TTS: VOLCENGINE_DIALOGUE_APP_ID=%r VOLCENGINE_ACCESS_TOKEN=%s",
            app_id or "(empty)",
            "set" if token else "(empty)",
        )
        return None

    speaker_id = settings.VOLCENGINE_DIALOGUE_SPEAKER_ID or "BV700_streaming"
    cluster = settings.VOLCENGINE_TTS_CLUSTER or "volcano_mega"
    payload = {
        "app": {"appid": app_id, "token": token, "cluster": cluster},
        "user": {"uid": "interview-trigger"},
        "audio": {
            "voice_type": speaker_id,
            "encoding": "pcm",
            "sample_rate": SEND_SAMPLE_RATE,   # 16kHz，匹配豆包实时对话输入格式
            "speed_ratio": 1.0,
            "volume_ratio": 1.0,
            "pitch_ratio": 1.0,
        },
        "request": {
            "reqid": str(uuid.uuid4()),
            "text": "你好",
            "text_type": "plain",
            "operation": "query",
        },
    }
    headers = {
        "Authorization": f"Bearer;{token}",
        "Content-Type": "application/json",
    }
    logger.info(
        "volcengine.trigger_tts.request",
        extra={"cluster": cluster, "voice_configured": bool(speaker_id)},
    )
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://openspeech.bytedance.com/api/v1/tts",
                json=payload,
                headers=headers,
            )
            logger.info(
                "volcengine.trigger_tts.response",
                extra={
                    "http_status": resp.status_code,
                    "response_chars": len(resp.text or ""),
                },
            )
            resp.raise_for_status()
            body = resp.json()
            code = body.get("code")
            if code != 3000:
                logger.warning(
                    "volcengine.trigger_tts.error",
                    extra={"provider_code": code},
                )
                return None
            audio_b64 = body.get("data")
            if not audio_b64:
                return None
            pcm = base64.b64decode(audio_b64)
            logger.info("Trigger TTS success: %d PCM bytes @ 16kHz", len(pcm))
            return pcm
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "volcengine.trigger_tts.http_error",
            extra={"http_status": exc.response.status_code},
        )
    except Exception as exc:
        logger.warning("Trigger TTS failed: %s", exc)
    return None


# ── 服务类 ────────────────────────────────────────────────


class VolcengineVoiceService:
    """用于管理火山引擎端到端实时语音对话的 WebSocket 连接。"""

    # 火山引擎要求的固定 App Key，见文档 2.1 节
    _FIXED_APP_KEY = "PlgvMymc7f3tQnJ6"

    def __init__(self) -> None:
        """用于初始化当前对象。"""
        self.ws_url = settings.VOLCENGINE_DIALOGUE_WS_URL
        self.app_id = settings.VOLCENGINE_DIALOGUE_APP_ID
        self.access_key = settings.VOLCENGINE_DIALOGUE_ACCESS_KEY
        self.resource_id = settings.VOLCENGINE_DIALOGUE_RESOURCE_ID
        self.speaker_id = settings.VOLCENGINE_DIALOGUE_SPEAKER_ID.strip()

    def is_configured(self) -> bool:
        """用于判断configured。"""
        return bool(self.app_id and self.access_key)

    def _ensure_configured(self) -> None:
        """用于确保configured。"""
        if not self.is_configured():
            raise VolcengineConfigurationError(
                "Volcengine dialogue is not configured. "
                "Set VOLCENGINE_DIALOGUE_APP_ID and VOLCENGINE_DIALOGUE_ACCESS_KEY."
            )

    def build_headers(self, connect_id: str) -> Dict[str, str]:
        """用于构建请求头。"""
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
        greeting: str = "",
        bot_name: str = "面试官",
        interview_session_id: int | str | None = None,
        on_text_message: Callable[[str, str], None] | None = None,
    ) -> None:
        """在前端 WebSocket 和火山引擎之间双向代理音视数据。

        client_ws: Starlette/FastAPI WebSocket 对象（已 accept）。
        """
        self._ensure_configured()

        session_id = str(uuid.uuid4())
        connect_id = str(uuid.uuid4())

        headers = self.build_headers(connect_id)
        started_at = time.monotonic()
        session_label = str(interview_session_id or "-")
        logger.info(
            (
                "voice.proxy.start interview_session_id=%s volc_session_id=%s "
                "connect_id=%s system_role_chars=%d greeting_chars=%d"
            ),
            session_label,
            session_id,
            connect_id,
            len(system_role),
            len(greeting),
        )
        connect_started_at = time.monotonic()

        try:
            ws_ctx = websockets.connect(
                self.ws_url,
                additional_headers=headers,
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
                        "volcengine.probe.failed",
                        extra={
                            "http_status": probe_resp.status_code,
                            "response_chars": len(probe_resp.text or ""),
                        },
                    )
            except Exception as probe_exc:
                logger.error("Volcengine probe also failed: %s", probe_exc)
            raise

        try:
            # 1) Start connection
            await volc_ws.send(_build_start_connection())
            resp = await volc_ws.recv()
            parsed = _parse_server_message(_coerce_ws_bytes(resp))
            logger.info(
                (
                    "volcengine.connection.started provider_event=%s "
                    "elapsed_ms=%.2f"
                ),
                parsed.get("event") if parsed else None,
                _elapsed_ms(connect_started_at),
            )
            if not parsed or parsed.get("event") != EVENT_CONNECTION_STARTED:
                logger.error(
                    "volcengine.connection.failed",
                    extra={"provider_event": parsed.get("event") if parsed else None},
                )
                await client_ws.send_json(
                    {"type": "error", "message": "连接火山引擎失败"}
                )
                return

            # 2) Start session
            session_started_at = time.monotonic()
            await volc_ws.send(
                _build_start_session(
                    session_id,
                    bot_name=bot_name,
                    system_role=system_role,
                    speaker_id=self.speaker_id,
                )
            )
            resp = await volc_ws.recv()
            parsed = _parse_server_message(_coerce_ws_bytes(resp))
            logger.info(
                "volcengine.session.started provider_event=%s elapsed_ms=%.2f",
                parsed.get("event") if parsed else None,
                _elapsed_ms(session_started_at),
            )
            if not parsed or parsed.get("event") != EVENT_SESSION_STARTED:
                logger.error(
                    "volcengine.session.failed",
                    extra={"provider_event": parsed.get("event") if parsed else None},
                )
                await client_ws.send_json(
                    {"type": "error", "message": "启动语音会话失败"}
                )
                await volc_ws.send(_build_finish_connection())
                return

            await client_ws.send_json({"type": "ready", "session_id": session_id})
            logger.info(
                "voice.proxy.ready interview_session_id=%s elapsed_ms=%.2f",
                session_label,
                _elapsed_ms(started_at),
            )

            # Event 300 SayHello：直接让豆包用自己的声音说开场白，无需外部 TTS
            if greeting:
                await volc_ws.send(_build_say_hello_frame(session_id, greeting))
                if on_text_message:
                    on_text_message("interviewer", greeting)
                await client_ws.send_json(
                    {
                        "type": "greeting",
                        "role": "interviewer",
                        "text": greeting,
                    }
                )
                logger.info(
                    "volcengine.greeting.sent greeting_chars=%d elapsed_ms=%.2f",
                    len(greeting),
                    _elapsed_ms(started_at),
                )

            closing = asyncio.Event()

            async def forward_to_volcengine():
                """用于转发to火山引擎。"""
                chunk_count = 0
                voiced_chunk_count = 0
                first_audio_ms: float | None = None
                first_voiced_ms: float | None = None
                max_peak = 0
                max_rms = 0.0
                try:
                    while not closing.is_set():
                        msg = await client_ws.receive()
                        if msg["type"] == "websocket.disconnect":
                            break
                        if msg["type"] == "websocket.receive":
                            if "bytes" in msg and msg["bytes"]:
                                pcm_stats = _describe_pcm16(msg["bytes"])
                                peak = int(pcm_stats["peak"])
                                rms = float(pcm_stats["rms"])
                                max_peak = max(max_peak, peak)
                                max_rms = max(max_rms, rms)
                                if first_audio_ms is None:
                                    first_audio_ms = _elapsed_ms(started_at)
                                    logger.info(
                                        (
                                            "voice.upstream.first_audio "
                                            "interview_session_id=%s chunk=%d "
                                            "elapsed_ms=%.2f bytes=%d peak=%d rms=%.2f"
                                        ),
                                        session_label,
                                        chunk_count + 1,
                                        first_audio_ms,
                                        len(msg["bytes"]),
                                        peak,
                                        rms,
                                    )
                                if peak >= VOICE_PEAK_THRESHOLD:
                                    voiced_chunk_count += 1
                                    if first_voiced_ms is None:
                                        first_voiced_ms = _elapsed_ms(started_at)
                                        logger.info(
                                            (
                                                "voice.upstream.first_voiced_audio "
                                                "interview_session_id=%s chunk=%d "
                                                "elapsed_ms=%.2f peak=%d rms=%.2f"
                                            ),
                                            session_label,
                                            chunk_count + 1,
                                            first_voiced_ms,
                                            peak,
                                            rms,
                                        )
                                await volc_ws.send(
                                    _build_audio_frame(session_id, msg["bytes"])
                                )
                                chunk_count += 1
                                if logger.isEnabledFor(logging.DEBUG) and (
                                    chunk_count <= 3 or chunk_count % 100 == 0
                                ):
                                    logger.debug(
                                        (
                                            "Sent audio chunk #%d (%d bytes) "
                                            "to Volcengine pcm=%s voiced_chunks=%d"
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
                    if chunk_count and not voiced_chunk_count:
                        logger.warning(
                            (
                                "voice.upstream.no_voiced_audio "
                                "interview_session_id=%s chunks=%d "
                                "max_peak=%d max_rms=%.2f threshold=%d"
                            ),
                            session_label,
                            chunk_count,
                            max_peak,
                            max_rms,
                            VOICE_PEAK_THRESHOLD,
                        )
                    logger.info(
                        (
                            "voice.upstream.done interview_session_id=%s "
                            "chunks=%d voiced_chunks=%d first_audio_ms=%s "
                            "first_voiced_ms=%s max_peak=%d max_rms=%.2f"
                        ),
                        session_label,
                        chunk_count,
                        voiced_chunk_count,
                        first_audio_ms,
                        first_voiced_ms,
                        max_peak,
                        max_rms,
                    )
                    closing.set()
                    try:
                        await volc_ws.send(_build_finish_session(session_id))
                        await asyncio.sleep(0.1)
                        await volc_ws.send(_build_finish_connection())
                    except Exception:
                        pass

            async def forward_to_client():
                """用于转发to客户端。"""
                msg_count = 0
                event_counts: dict[int, int] = {}
                tts_audio_chunks = 0
                tts_audio_bytes = 0
                first_provider_msg_ms: float | None = None
                first_tts_audio_ms: float | None = None
                first_asr_text_ms: float | None = None
                first_asr_final_ms: float | None = None
                first_chat_text_ms: float | None = None
                first_chat_final_ms: float | None = None
                pending_text_by_role: dict[str, str] = {}
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
                            if isinstance(event, int):
                                event_counts[event] = event_counts.get(event, 0) + 1
                            if first_provider_msg_ms is None:
                                first_provider_msg_ms = _elapsed_ms(started_at)
                                logger.info(
                                    (
                                        "voice.downstream.first_provider_msg "
                                        "interview_session_id=%s event=%s "
                                        "elapsed_ms=%.2f"
                                    ),
                                    session_label,
                                    event,
                                    first_provider_msg_ms,
                                )

                            if (
                                logger.isEnabledFor(logging.DEBUG)
                                and msg_count <= 10
                            ):
                                logger.debug(
                                    (
                                        "Volcengine msg #%d: event=%s data=%s "
                                        "raw_bytes=%d audio_bytes=%d"
                                    ),
                                    msg_count,
                                    event,
                                    parsed.get("data", {}),
                                    len(parsed.get("raw", b"") or b""),
                                    len(parsed.get("audio", b"") or b""),
                                )

                            if event == EVENT_TTS_RESPONSE:
                                audio = parsed.get("audio", b"")
                                if audio:
                                    tts_audio_chunks += 1
                                    tts_audio_bytes += len(audio)
                                    if first_tts_audio_ms is None:
                                        first_tts_audio_ms = _elapsed_ms(started_at)
                                        logger.info(
                                            (
                                                "voice.downstream.first_tts_audio "
                                                "interview_session_id=%s "
                                                "elapsed_ms=%.2f bytes=%d"
                                            ),
                                            session_label,
                                            first_tts_audio_ms,
                                            len(audio),
                                        )
                                    await client_ws.send_bytes(audio)
                            elif event in (
                                EVENT_ASR_RESPONSE,
                                EVENT_ASR_INFO,
                                EVENT_ASR_ENDED,
                                EVENT_CHAT_RESPONSE,
                                EVENT_CHAT_ENDED,
                            ):
                                event_data = parsed.get("data", {})
                                raw_text = _extract_realtime_text(event_data)
                                is_final = _extract_is_final(event_data) or event in (
                                    EVENT_ASR_ENDED,
                                    EVENT_CHAT_ENDED,
                                )
                                role = _realtime_event_role(event)
                                text = _realtime_text_with_pending(
                                    role=role,
                                    text=raw_text,
                                    is_final=is_final,
                                    pending_by_role=pending_text_by_role,
                                )
                                if event in (
                                    EVENT_ASR_RESPONSE,
                                    EVENT_ASR_INFO,
                                    EVENT_ASR_ENDED,
                                ):
                                    if text and first_asr_text_ms is None:
                                        first_asr_text_ms = _elapsed_ms(started_at)
                                        logger.info(
                                            (
                                                "voice.downstream.first_asr_text "
                                                "interview_session_id=%s "
                                                "elapsed_ms=%.2f final=%s"
                                            ),
                                            session_label,
                                            first_asr_text_ms,
                                            is_final,
                                        )
                                    if is_final and first_asr_final_ms is None:
                                        first_asr_final_ms = _elapsed_ms(started_at)
                                        logger.info(
                                            (
                                                "voice.downstream.first_asr_final "
                                                "interview_session_id=%s "
                                                "elapsed_ms=%.2f text_chars=%d"
                                            ),
                                            session_label,
                                            first_asr_final_ms,
                                            len(text or ""),
                                        )
                                if event in (EVENT_CHAT_RESPONSE, EVENT_CHAT_ENDED):
                                    if text and first_chat_text_ms is None:
                                        first_chat_text_ms = _elapsed_ms(started_at)
                                        logger.info(
                                            (
                                                "voice.downstream.first_chat_text "
                                                "interview_session_id=%s "
                                                "elapsed_ms=%.2f final=%s"
                                            ),
                                            session_label,
                                            first_chat_text_ms,
                                            is_final,
                                        )
                                    if is_final and first_chat_final_ms is None:
                                        first_chat_final_ms = _elapsed_ms(started_at)
                                        logger.info(
                                            (
                                                "voice.downstream.first_chat_final "
                                                "interview_session_id=%s "
                                                "elapsed_ms=%.2f text_chars=%d"
                                            ),
                                            session_label,
                                            first_chat_final_ms,
                                            len(text or ""),
                                        )
                                if on_text_message and role and text and is_final:
                                    on_text_message(role, text)
                                if role and is_final:
                                    pending_text_by_role.pop(role, None)
                                await client_ws.send_json(
                                    {
                                        "type": "event",
                                        "event": event,
                                        "data": event_data,
                                        "text": text,
                                        "is_final": is_final,
                                        "turn_id": event_data.get("reqid")
                                        or event_data.get("trace_id")
                                        or f"{event}-{msg_count}",
                                    }
                                )
                            elif event in (
                                EVENT_SESSION_FINISHED,
                                EVENT_CONNECTION_FINISHED,
                                EVENT_SESSION_FAILED,
                            ):
                                await client_ws.send_json(
                                    {
                                        "type": "event",
                                        "event": event,
                                    }
                                )
                                return
                except Exception as exc:
                    logger.warning("forward_to_client error: %s", exc)
                finally:
                    logger.info(
                        (
                            "voice.downstream.done interview_session_id=%s "
                            "messages=%d event_counts=%s tts_chunks=%d "
                            "tts_bytes=%d first_provider_msg_ms=%s "
                            "first_tts_audio_ms=%s first_asr_text_ms=%s "
                            "first_asr_final_ms=%s first_chat_text_ms=%s "
                            "first_chat_final_ms=%s elapsed_ms=%.2f"
                        ),
                        session_label,
                        msg_count,
                        json.dumps(event_counts, ensure_ascii=False, sort_keys=True),
                        tts_audio_chunks,
                        tts_audio_bytes,
                        first_provider_msg_ms,
                        first_tts_audio_ms,
                        first_asr_text_ms,
                        first_asr_final_ms,
                        first_chat_text_ms,
                        first_chat_final_ms,
                        _elapsed_ms(started_at),
                    )
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
