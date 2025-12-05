"""
语音识别服务模块

提供统一的ASR（Automatic Speech Recognition）接口，
使用火山引擎大模型流式语音识别服务（WebSocket协议）。
"""

import asyncio
import gzip
import json
import struct
import uuid
import logging
from typing import Dict, Any, Union, Optional
from enum import Enum
import websockets
from app.core.config import settings

logger = logging.getLogger(__name__)


class ASRProvider(str, Enum):
    """ASR服务提供商枚举"""

    VOLCENGINE = "volcengine"
    VOLCENGINE_BIGMODEL = "volcengine_bigmodel"


class VolcengineASRProtocol:
    """
    火山引擎大模型流式语音识别协议实现

    基于 WebSocket 二进制协议，参考文档：
    https://www.volcengine.com/docs/6561/1354869
    """

    # 协议版本
    PROTOCOL_VERSION = 0b0001

    # Header 大小（4字节）
    HEADER_SIZE = 0b0001

    # 消息类型
    MSG_TYPE_FULL_CLIENT_REQUEST = 0b0001
    MSG_TYPE_AUDIO_ONLY_REQUEST = 0b0010
    MSG_TYPE_FULL_SERVER_RESPONSE = 0b1001
    MSG_TYPE_ERROR_RESPONSE = 0b1111

    # 消息类型标志
    MSG_FLAG_NONE = 0b0000
    MSG_FLAG_POSITIVE_SEQUENCE = 0b0001
    MSG_FLAG_LAST_PACKET_NO_SEQ = 0b0010
    MSG_FLAG_LAST_PACKET_WITH_SEQ = 0b0011

    # 序列化方法
    SERIALIZATION_NONE = 0b0000
    SERIALIZATION_JSON = 0b0001

    # 压缩方法
    COMPRESSION_NONE = 0b0000
    COMPRESSION_GZIP = 0b0001

    @classmethod
    def build_header(
        cls,
        msg_type: int,
        msg_flags: int = 0b0000,
        serialization: int = 0b0001,
        compression: int = 0b0001,
    ) -> bytes:
        """构建4字节协议头"""
        byte0 = (cls.PROTOCOL_VERSION << 4) | cls.HEADER_SIZE
        byte1 = (msg_type << 4) | msg_flags
        byte2 = (serialization << 4) | compression
        byte3 = 0x00  # 保留字节
        return bytes([byte0, byte1, byte2, byte3])

    @classmethod
    def build_full_client_request(cls, payload: dict, use_gzip: bool = True) -> bytes:
        """构建 full client request 消息"""
        header = cls.build_header(
            msg_type=cls.MSG_TYPE_FULL_CLIENT_REQUEST,
            msg_flags=cls.MSG_FLAG_NONE,
            serialization=cls.SERIALIZATION_JSON,
            compression=cls.COMPRESSION_GZIP if use_gzip else cls.COMPRESSION_NONE,
        )

        payload_bytes = json.dumps(payload).encode("utf-8")
        if use_gzip:
            payload_bytes = gzip.compress(payload_bytes)

        payload_size = struct.pack(">I", len(payload_bytes))

        return header + payload_size + payload_bytes

    @classmethod
    def build_audio_request(
        cls, audio_data: bytes, is_last: bool = False, use_gzip: bool = True
    ) -> bytes:
        """构建 audio only request 消息"""
        msg_flags = cls.MSG_FLAG_LAST_PACKET_NO_SEQ if is_last else cls.MSG_FLAG_NONE

        header = cls.build_header(
            msg_type=cls.MSG_TYPE_AUDIO_ONLY_REQUEST,
            msg_flags=msg_flags,
            serialization=cls.SERIALIZATION_NONE,
            compression=cls.COMPRESSION_GZIP if use_gzip else cls.COMPRESSION_NONE,
        )

        payload_bytes = gzip.compress(audio_data) if use_gzip else audio_data
        payload_size = struct.pack(">I", len(payload_bytes))

        return header + payload_size + payload_bytes

    @classmethod
    def parse_response(cls, data: bytes) -> Dict[str, Any]:
        """解析服务器响应"""
        if len(data) < 4:
            raise ValueError("响应数据太短")

        # 解析头部
        byte0, byte1, byte2, _ = data[0], data[1], data[2], data[3]

        protocol_version = (byte0 >> 4) & 0x0F
        header_size = (byte0 & 0x0F) * 4
        msg_type = (byte1 >> 4) & 0x0F
        msg_flags = byte1 & 0x0F
        serialization = (byte2 >> 4) & 0x0F
        compression = byte2 & 0x0F

        result = {
            "protocol_version": protocol_version,
            "header_size": header_size,
            "msg_type": msg_type,
            "msg_flags": msg_flags,
            "serialization": serialization,
            "compression": compression,
        }

        # 解析 payload
        offset = header_size

        # 错误响应
        if msg_type == cls.MSG_TYPE_ERROR_RESPONSE:
            if len(data) >= offset + 8:
                error_code = struct.unpack(">I", data[offset : offset + 4])[0]
                error_size = struct.unpack(">I", data[offset + 4 : offset + 8])[0]
                error_msg = data[offset + 8 : offset + 8 + error_size].decode("utf-8")
                result["error_code"] = error_code
                result["error_message"] = error_msg
            return result

        # Full server response
        if msg_type == cls.MSG_TYPE_FULL_SERVER_RESPONSE:
            # 可能有 sequence number
            if msg_flags in (
                cls.MSG_FLAG_POSITIVE_SEQUENCE,
                cls.MSG_FLAG_LAST_PACKET_WITH_SEQ,
            ):
                if len(data) >= offset + 4:
                    sequence = struct.unpack(">i", data[offset : offset + 4])[0]
                    result["sequence"] = sequence
                    offset += 4

            # 解析 payload size 和 payload
            if len(data) >= offset + 4:
                payload_size = struct.unpack(">I", data[offset : offset + 4])[0]
                offset += 4

                payload_bytes = data[offset : offset + payload_size]

                # 解压
                if compression == cls.COMPRESSION_GZIP:
                    try:
                        payload_bytes = gzip.decompress(payload_bytes)
                    except Exception as e:
                        logger.warning(f"GZIP解压失败: {e}")

                # 反序列化
                if serialization == cls.SERIALIZATION_JSON:
                    try:
                        result["payload"] = json.loads(payload_bytes.decode("utf-8"))
                    except Exception as e:
                        logger.warning(f"JSON解析失败: {e}")
                        result["payload_raw"] = payload_bytes
                else:
                    result["payload_raw"] = payload_bytes

        return result


class ASRService:
    """统一ASR服务类，使用火山引擎大模型流式语音识别"""

    def __init__(self, provider: ASRProvider = ASRProvider.VOLCENGINE_BIGMODEL):
        """初始化ASR服务"""
        self.provider = provider
        self._setup_provider()

    def _setup_provider(self):
        """配置连接参数"""
        # 使用火山引擎大模型流式语音识别
        self.app_key = settings.VOLCENGINE_APP_KEY
        self.access_token = settings.VOLCENGINE_ACCESS_TOKEN
        self.resource_id = settings.VOLCENGINE_ASR_RESOURCE_ID

        # WebSocket 端点
        # 双向流式模式（更快，适合面试场景）
        self.ws_url = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel"

        # 备用：流式输入模式（更准确，但较慢）
        # self.ws_url = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_nostream"

        # 为了向后兼容，也设置这些属性
        self.api_key = self.access_token
        self.app_id = self.app_key
        self.model = "bigmodel"

    async def recognize_speech(
        self,
        audio_data: bytes,
        format: str = "pcm",
        sample_rate: int = 16000,
        language: str = "zh-CN",
        **kwargs,
    ) -> Dict[str, Any]:
        """
        识别语音

        Args:
            audio_data: 音频数据（bytes）
            format: 音频格式（pcm, wav, mp3, ogg）
            sample_rate: 采样率（默认16000）
            language: 语言代码
            **kwargs: 其他参数

        Returns:
            识别结果，包含文本和置信度
        """
        if not self.app_key or not self.access_token:
            raise ValueError("未配置火山引擎 APP_KEY 或 ACCESS_TOKEN")

        # 生成连接ID
        connect_id = str(uuid.uuid4())

        # 构建请求头
        headers = {
            "X-Api-App-Key": self.app_key,
            "X-Api-Access-Key": self.access_token,
            "X-Api-Resource-Id": self.resource_id,
            "X-Api-Connect-Id": connect_id,
        }

        # 构建请求参数
        request_payload = {
            "user": {"uid": f"user_{uuid.uuid4().hex[:8]}"},
            "audio": {
                "format": format,
                "rate": sample_rate,
                "bits": 16,
                "channel": 1,
                "codec": "raw"
                if format in ("pcm", "wav")
                else "opus"
                if format == "ogg"
                else "raw",
            },
            "request": {
                "model_name": "bigmodel",
                "enable_itn": True,
                "enable_punc": True,
                "enable_ddc": False,
                "show_utterances": True,
                "result_type": "full",
            },
        }

        # 如果指定了语言，添加到请求中（仅 nostream 模式支持）
        if language and "nostream" in self.ws_url:
            # 目前主要支持中英文，其他语言可能需要特定配置
            pass

        try:
            result_text = ""
            confidence = 0.95

            async with websockets.connect(
                self.ws_url,
                extra_headers=headers,
                ping_interval=None,
                close_timeout=30,
            ) as ws:
                logger.info(f"WebSocket 已连接: {connect_id}")

                # 1. 发送 full client request
                full_request = VolcengineASRProtocol.build_full_client_request(
                    request_payload
                )
                await ws.send(full_request)
                logger.debug("已发送 full client request")

                # 等待服务器确认
                response_data = await asyncio.wait_for(ws.recv(), timeout=10)
                response = VolcengineASRProtocol.parse_response(response_data)
                logger.debug(f"收到服务器响应: {response}")

                if (
                    response.get("msg_type")
                    == VolcengineASRProtocol.MSG_TYPE_ERROR_RESPONSE
                ):
                    error_msg = response.get("error_message", "未知错误")
                    error_code = response.get("error_code", 0)
                    raise Exception(f"ASR服务错误 ({error_code}): {error_msg}")

                # 2. 发送音频数据
                # 将音频分块发送（每块约200ms，16kHz 16bit = 6400 bytes）
                chunk_size = 6400
                total_chunks = (len(audio_data) + chunk_size - 1) // chunk_size

                # 创建发送和接收任务
                async def send_audio():
                    """发送音频数据"""
                    for i in range(0, len(audio_data), chunk_size):
                        chunk = audio_data[i : i + chunk_size]
                        is_last = i + chunk_size >= len(audio_data)

                        audio_request = VolcengineASRProtocol.build_audio_request(
                            chunk, is_last=is_last
                        )
                        await ws.send(audio_request)

                        if is_last:
                            logger.debug(f"已发送最后一包音频 (总共 {total_chunks} 包)")

                        # 短暂延迟避免发送过快
                        await asyncio.sleep(0.05)

                async def receive_results():
                    """接收识别结果"""
                    text = ""
                    try:
                        while True:
                            try:
                                response_data = await asyncio.wait_for(ws.recv(), timeout=30)
                            except asyncio.TimeoutError:
                                logger.warning("接收识别结果超时")
                                break
                            except websockets.exceptions.ConnectionClosedOK:
                                logger.info("WebSocket 正常关闭")
                                break

                            response = VolcengineASRProtocol.parse_response(response_data)

                            if (
                                response.get("msg_type")
                                == VolcengineASRProtocol.MSG_TYPE_ERROR_RESPONSE
                            ):
                                error_msg = response.get("error_message", "未知错误")
                                error_code = response.get("error_code", 0)
                                logger.error(f"ASR服务错误 ({error_code}): {error_msg}")
                                raise Exception(f"ASR服务错误 ({error_code}): {error_msg}")

                            # 提取识别结果
                            payload = response.get("payload", {})
                            if isinstance(payload, dict):
                                result = payload.get("result", {})
                                if isinstance(result, dict):
                                    current_text = result.get("text", "")
                                    if current_text:
                                        text = current_text
                                        logger.debug(f"识别中间结果: {current_text}")
                                elif isinstance(result, list) and result:
                                    # 有时结果是列表格式
                                    texts = [
                                        r.get("text", "")
                                        for r in result
                                        if isinstance(r, dict)
                                    ]
                                    if texts:
                                        text = "".join(texts)

                            # 检查消息标志，判断是否是最后一包
                            msg_flags = response.get("msg_flags", 0)
                            if msg_flags in (
                                VolcengineASRProtocol.MSG_FLAG_LAST_PACKET_NO_SEQ,
                                VolcengineASRProtocol.MSG_FLAG_LAST_PACKET_WITH_SEQ,
                            ):
                                logger.debug("收到最终识别结果")
                                break

                    except websockets.exceptions.ConnectionClosedOK:
                        logger.info("WebSocket 正常关闭")
                    except websockets.exceptions.ConnectionClosedError as e:
                        logger.error(f"WebSocket 异常关闭: {e}")
                        raise
                    except Exception as e:
                        logger.error(f"接收识别结果异常: {e}")
                        raise
                    return text

                # 并发执行发送和接收
                send_task = asyncio.create_task(send_audio())
                receive_task = asyncio.create_task(receive_results())

                # 等待发送完成
                await send_task

                # 等待接收完成并获取结果
                result_text = await receive_task

                logger.info(
                    f"语音识别完成: {result_text[:50]}..."
                    if len(result_text) > 50
                    else f"语音识别完成: {result_text}"
                )

            return {
                "text": result_text,
                "confidence": confidence,
                "provider": self.provider.value,
                "model": self.model,
                "alternatives": [],
                "word_timings": [],
                "speaker_labels": [],
            }

        except Exception as e:
            error_str = str(e)
            # WebSocket 正常关闭不算错误
            if "1000" in error_str and "OK" in error_str:
                logger.info("WebSocket 正常关闭")
                # 如果有识别结果就返回，否则返回空
                if result_text:
                    return {
                        "text": result_text,
                        "confidence": confidence,
                        "provider": self.provider.value,
                        "model": self.model,
                        "alternatives": [],
                        "word_timings": [],
                        "speaker_labels": [],
                    }
                else:
                    raise Exception("未获取到识别结果")

            logger.error(f"ASR服务请求异常: {error_str}")
            raise Exception(f"ASR服务请求异常: {error_str}")

    def switch_provider(self, provider: ASRProvider):
        """切换ASR服务提供商"""
        self.provider = provider
        self._setup_provider()

    def get_provider_info(self) -> Dict[str, Any]:
        """获取当前提供商信息"""
        return {
            "provider": self.provider.value,
            "model": self.model,
            "ws_url": self.ws_url,
            "features": {
                "streaming": True,
                "speaker_diarization": False,
                "word_timestamps": True,
                "language_detection": True,
                "noise_reduction": True,
            },
        }
