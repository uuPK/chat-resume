"""
语音识别服务模块

提供统一的ASR（Automatic Speech Recognition）接口，整合多个语音识别服务提供商。
支持火山引擎等多种ASR服务。
"""

import httpx
import json
from typing import Dict, Any, BinaryIO, Union
from enum import Enum
from app.core.config import settings


class ASRProvider(str, Enum):
    """ASR服务提供商枚举"""

    VOLCENGINE = "volcengine"
    VOLCENGINE_BIGMODEL = "volcengine_bigmodel"
    AZURE = "azure"


class ASRService:
    """统一ASR服务类，支持多种语音识别提供商"""

    def __init__(self, provider: ASRProvider = ASRProvider.VOLCENGINE_BIGMODEL):
        """初始化ASR服务

        Args:
            provider: ASR服务提供商，默认使用火山引擎大模型
        """
        self.provider = provider
        self._setup_provider()

    def _setup_provider(self):
        """根据选择的提供商配置连接参数"""
        if self.provider == ASRProvider.VOLCENGINE:
            self.api_key = settings.VOLCENGINE_ASR_API_KEY
            self.app_id = settings.VOLCENGINE_ASR_APP_ID
            self.api_base = "https://openspeech.bytedance.com/api/v1/vc"
            self.model = "instant_recognition"
            self.headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
        elif self.provider == ASRProvider.VOLCENGINE_BIGMODEL:
            self.api_key = settings.VOLCENGINE_BIGMODEL_API_KEY
            self.app_id = settings.VOLCENGINE_BIGMODEL_APP_ID
            self.api_base = "https://ark.cn-beijing.volces.com/api/v3"
            self.model = "doubao-voice"
            self.headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

    async def recognize_speech(
        self,
        audio_data: Union[bytes, BinaryIO],
        audio_format: str = "mp3",
        sample_rate: int = 16000,
        language: str = "zh-CN",
        **kwargs,
    ) -> Dict[str, Any]:
        """识别语音

        Args:
            audio_data: 音频数据或文件对象
            audio_format: 音频格式（mp3, wav, pcm, flac）
            sample_rate: 采样率
            language: 语言代码
            **kwargs: 其他参数

        Returns:
            识别结果，包含文本和置信度
        """
        if not self.api_key:
            raise ValueError(f"未配置 {self.provider.value} API密钥")

        if self.provider == ASRProvider.VOLCENGINE_BIGMODEL:
            return await self._recognize_with_bigmodel(
                audio_data, audio_format, sample_rate, language, **kwargs
            )
        else:
            return await self._recognize_with_standard(
                audio_data, audio_format, sample_rate, language, **kwargs
            )

    async def _recognize_with_bigmodel(
        self,
        audio_data: Union[bytes, BinaryIO],
        audio_format: str,
        sample_rate: int,
        language: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """使用大模型进行语音识别"""
        # 将音频数据转换为base64
        if isinstance(audio_data, bytes):
            import base64

            audio_base64 = base64.b64encode(audio_data).decode("utf-8")
        else:
            audio_base64 = None

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "请识别这段音频中的文字内容"},
                        {
                            "type": "audio",
                            "audio": {"data": audio_base64, "format": audio_format},
                        },
                    ],
                }
            ],
            "temperature": 0.1,
            "max_tokens": 1000,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.api_base}/chat/completions",
                    json=payload,
                    headers=self.headers,
                )
                response.raise_for_status()
                return self._parse_bigmodel_response(response.json())

        except httpx.HTTPStatusError as e:
            raise Exception(
                f"ASR服务请求失败: {e.response.status_code} - {e.response.text}"
            )
        except Exception as e:
            raise Exception(f"ASR服务请求异常: {str(e)}")

    async def _recognize_with_standard(
        self,
        audio_data: Union[bytes, BinaryIO],
        audio_format: str,
        sample_rate: int,
        language: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """使用标准接口进行语音识别"""
        payload = {
            "app": {
                "appid": self.app_id,
                "token": self.api_key,
                "cluster": "volcengine_common",
            },
            "user": {"uid": "user_001"},
            "audio": {
                "format": audio_format,
                "rate": sample_rate,
                "bits": 16,
                "channel": 1,
            },
            "request": {
                "reqid": f"req_{int(__import__('time').time() * 1000)}",
                "nbest": 1,
                "continuous": False,
                "show_speakers": kwargs.get("show_speakers", False),
                "language": language,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if isinstance(audio_data, bytes):
                    files = {
                        "audio": ("audio.mp3", audio_data, f"audio/{audio_format}")
                    }
                else:
                    files = {"audio": audio_data}

                response = await client.post(
                    f"{self.api_base}/submit",
                    data={"payload": json.dumps(payload)},
                    files=files,
                    headers=self.headers,
                )
                response.raise_for_status()

                # 获取识别结果
                result = response.json()
                task_id = result.get("data", {}).get("task_id")

                if task_id:
                    return await self._get_recognition_result(task_id)

                return self._parse_standard_response(result)

        except httpx.HTTPStatusError as e:
            raise Exception(
                f"ASR服务请求失败: {e.response.status_code} - {e.response.text}"
            )
        except Exception as e:
            raise Exception(f"ASR服务请求异常: {str(e)}")

    async def _get_recognition_result(self, task_id: str) -> Dict[str, Any]:
        """获取识别结果"""
        import time

        max_attempts = 30
        attempt = 0

        while attempt < max_attempts:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.api_base}/query",
                        params={"task_id": task_id},
                        headers=self.headers,
                    )
                    response.raise_for_status()

                    result = response.json()
                    status = result.get("data", {}).get("status")

                    if status == "success":
                        return self._parse_standard_response(result)
                    elif status == "failed":
                        raise Exception(
                            f"语音识别失败: {result.get('data', {}).get('message', '未知错误')}"
                        )

                    time.sleep(1)
                    attempt += 1

            except Exception as e:
                if attempt == max_attempts - 1:
                    raise e
                attempt += 1
                time.sleep(1)

        raise Exception("语音识别超时")

    def _parse_bigmodel_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """解析大模型响应"""
        try:
            content = (
                response.get("choices", [{}])[0].get("message", {}).get("content", "")
            )
            return {
                "text": content,
                "confidence": 0.95,
                "provider": self.provider.value,
                "model": self.model,
                "alternatives": [],
                "word_timings": [],
                "speaker_labels": [],
            }
        except Exception as e:
            raise Exception(f"解析响应失败: {str(e)}")

    def _parse_standard_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """解析标准响应"""
        try:
            data = response.get("data", {})
            result = data.get("result", [])

            if not result:
                return {
                    "text": "",
                    "confidence": 0.0,
                    "provider": self.provider.value,
                    "model": self.model,
                    "alternatives": [],
                    "word_timings": [],
                    "speaker_labels": [],
                }

            # 合并所有片段
            text_parts = []
            confidence_scores = []
            word_timings = []

            for segment in result:
                text_parts.append(segment.get("text", ""))
                confidence_scores.append(segment.get("confidence", 0.0))

                # 处理词级别时间戳
                if "words" in segment:
                    for word in segment["words"]:
                        word_timings.append(
                            {
                                "word": word.get("word", ""),
                                "start": word.get("start", 0),
                                "end": word.get("end", 0),
                                "confidence": word.get("confidence", 0.0),
                            }
                        )

            full_text = "".join(text_parts)
            avg_confidence = (
                sum(confidence_scores) / len(confidence_scores)
                if confidence_scores
                else 0.0
            )

            return {
                "text": full_text,
                "confidence": avg_confidence,
                "provider": self.provider.value,
                "model": self.model,
                "alternatives": [],  # 简化实现
                "word_timings": word_timings,
                "speaker_labels": [],  # 简化实现
            }

        except Exception as e:
            raise Exception(f"解析响应失败: {str(e)}")

    async def stream_recognize(
        self, audio_stream: BinaryIO, chunk_size: int = 1024, **kwargs
    ):
        """流式语音识别

        Args:
            audio_stream: 音频流
            chunk_size: 块大小
            **kwargs: 其他参数

        Yields:
            识别结果
        """
        # 简化实现，实际需要根据具体API进行调整
        chunks = []
        while True:
            chunk = audio_stream.read(chunk_size)
            if not chunk:
                break
            chunks.append(chunk)

        audio_data = b"".join(chunks)
        result = await self.recognize_speech(audio_data, **kwargs)
        yield result

    def switch_provider(self, provider: ASRProvider):
        """切换ASR服务提供商

        Args:
            provider: 新的ASR服务提供商
        """
        self.provider = provider
        self._setup_provider()

    def get_provider_info(self) -> Dict[str, Any]:
        """获取当前提供商信息"""
        return {
            "provider": self.provider.value,
            "model": self.model,
            "api_base": self.api_base,
            "features": self._get_provider_features(),
        }

    def _get_provider_features(self) -> Dict[str, bool]:
        """获取提供商特性"""
        features = {
            "streaming": False,
            "speaker_diarization": False,
            "word_timestamps": False,
            "language_detection": False,
            "noise_reduction": True,
        }

        if self.provider == ASRProvider.VOLCENGINE_BIGMODEL:
            features.update(
                {
                    "streaming": False,
                    "word_timestamps": False,
                    "language_detection": True,
                    "noise_reduction": True,
                }
            )
        elif self.provider == ASRProvider.VOLCENGINE:
            features.update(
                {
                    "streaming": False,
                    "word_timestamps": True,
                    "language_detection": False,
                    "noise_reduction": True,
                }
            )

        return features
