"""
文字转语音服务模块

提供统一的TTS（Text-to-Speech）接口，整合多个语音合成服务提供商。
支持MiniMax等多种TTS服务。
"""

import httpx
from typing import Dict, Any, Optional
from enum import Enum
from app.infra.config import settings


class TTSProvider(str, Enum):
    """TTS服务提供商枚举"""

    MINIMAX = "minimax"
    VOLCENGINE = "volcengine"
    AZURE = "azure"


class TTSService:
    """统一TTS服务类，支持多种语音合成提供商"""

    def __init__(self, provider: TTSProvider = TTSProvider.MINIMAX):
        """初始化TTS服务

        Args:
            provider: TTS服务提供商，默认使用MiniMax
        """
        self.provider = provider
        self._setup_provider()

    def _setup_provider(self):
        """根据选择的提供商配置连接参数"""
        if self.provider == TTSProvider.MINIMAX:
            self.api_key = settings.MINIMAX_API_KEY
            self.group_id = settings.MINIMAX_GROUP_ID
            # 使用配置的API_BASE，默认为中国大陆端点
            self.api_base = settings.MINIMAX_API_BASE or "https://api.minimaxi.chat"
            self.model = "speech-02-hd"  # 使用更新的模型
            self.headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
        elif self.provider == TTSProvider.VOLCENGINE:
            self.api_key = settings.VOLCENGINE_TTS_API_KEY
            self.app_id = settings.VOLCENGINE_TTS_APP_ID
            self.api_base = "https://openspeech.bytedance.com/api/v1/tts"
            self.model = "doubao-voice"
            self.headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

    async def synthesize_speech(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: float = 1.0,
        pitch: float = 1.0,
        format: str = "mp3",
        sample_rate: int = 24000,
    ) -> bytes:
        """合成语音

        Args:
            text: 要转换的文本
            voice: 语音类型，如未指定则使用默认语音
            speed: 语速，0.5-2.0
            pitch: 音调，0.5-2.0
            format: 输出格式（mp3, wav, pcm）
            sample_rate: 采样率

        Returns:
            语音数据的字节流
        """
        if not self.api_key:
            raise ValueError(f"未配置 {self.provider.value} API密钥")

        payload = self._build_tts_payload(
            text, voice, speed, pitch, format, sample_rate
        )
        url = self._get_tts_endpoint()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=self.headers)
                response.raise_for_status()

                if self.provider == TTSProvider.MINIMAX:
                    return await self._handle_minimax_response(response)
                else:
                    return response.content

        except httpx.HTTPStatusError as e:
            raise Exception(
                f"TTS服务请求失败: {e.response.status_code} - {e.response.text}"
            )
        except Exception as e:
            raise Exception(f"TTS服务请求异常: {str(e)}")

    async def get_available_voices(self) -> Dict[str, Any]:
        """获取可用的语音列表

        Returns:
            语音选项列表
        """
        if self.provider == TTSProvider.MINIMAX:
            return {
                "voices": {
                    "male": "male-qn-qingse",  # 清澈男声
                    "female": "female-shaonv",  # 少女音
                    "female2": "female-yujie",  # 御姐音
                },
                "default": "female-shaonv",
            }
        elif self.provider == TTSProvider.VOLCENGINE:
            return {
                "voices": {
                    "zh_female_1": "BV700_streaming",
                    "zh_female_2": "BV701_streaming",
                    "zh_male_1": "BV702_streaming",
                    "zh_male_2": "BV703_streaming",
                },
                "default": "BV700_streaming",
            }

        return {"voices": {}, "default": ""}

    async def synthesize_with_ssml(self, ssml: str, format: str = "mp3") -> bytes:
        """使用SSML合成语音

        Args:
            ssml: SSML格式的文本
            format: 输出格式

        Returns:
            语音数据的字节流
        """
        # 简化实现，实际需要根据不同提供商的SSML支持进行调整
        return await self.synthesize_speech(ssml, format=format)

    def _build_tts_payload(
        self,
        text: str,
        voice: Optional[str],
        speed: float,
        pitch: float,
        format: str,
        sample_rate: int,
    ) -> Dict[str, Any]:
        """构建TTS请求载荷"""
        payload: Dict[str, Any] = {
            "model": self.model,
            "text": text,
        }

        if self.provider == TTSProvider.MINIMAX:
            # 使用新的t2a_v2 API格式
            minimax_updates: Dict[str, Any] = {
                "voice_setting": {
                    "voice_id": voice or "female-shaonv",
                    "speed": speed,
                    "vol": 1.0,
                    "pitch": int(pitch),  # pitch在新API中是整数
                },
                "audio_setting": {
                    "sample_rate": sample_rate,
                    "format": format,
                    "bitrate": 128000,
                },
            }
            payload.update(minimax_updates)
        elif self.provider == TTSProvider.VOLCENGINE:
            volcengine_updates: Dict[str, Any] = {
                "voice": voice or "BV700_streaming",
                "speed": speed,
                "pitch": pitch,
                "rate": sample_rate,
                "format": format,
            }
            payload.update(volcengine_updates)

        return payload

    def _get_tts_endpoint(self) -> str:
        """获取TTS API端点URL"""
        if self.provider == TTSProvider.MINIMAX:
            # 使用新的t2a_v2端点
            return f"{self.api_base}/v1/t2a_v2?GroupId={self.group_id}"
        elif self.provider == TTSProvider.VOLCENGINE:
            return f"{self.api_base}/synthesis"

        raise ValueError(f"不支持的TTS提供商: {self.provider}")

    async def _handle_minimax_response(self, response: httpx.Response) -> bytes:
        """处理MiniMax的响应格式"""
        response_data = response.json()

        # 检查响应状态码
        base_resp = response_data.get("base_resp", {})
        status_code = base_resp.get("status_code", 0)

        if status_code != 0:
            error_msg = base_resp.get("status_msg", "未知错误")
            raise Exception(f"MiniMax TTS错误: {error_msg}")

        # 获取音频数据（十六进制编码字符串）
        audio_hex = response_data.get("data", {}).get("audio")
        if not audio_hex:
            # 尝试从audio_file字段直接获取
            audio_hex = response_data.get("audio_file")

        if not audio_hex:
            raise Exception("MiniMax TTS响应中没有音频数据")

        # MiniMax t2a_v2 API返回的是十六进制字符串，需要用fromhex解码
        return bytes.fromhex(audio_hex)

    def switch_provider(self, provider: TTSProvider):
        """切换TTS服务提供商

        Args:
            provider: 新的TTS服务提供商
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
        features: Dict[str, bool] = {
            "ssml_support": False,
            "voice_cloning": False,
            "emotion_control": False,
            "real_time_synthesis": True,
        }

        if self.provider == TTSProvider.MINIMAX:
            minimax_features: Dict[str, bool] = {
                "ssml_support": False,
                "emotion_control": True,
                "multiple_voices": True,
            }
            features.update(minimax_features)
        elif self.provider == TTSProvider.VOLCENGINE:
            volcengine_features: Dict[str, bool] = {
                "ssml_support": True,
                "emotion_control": False,
                "multiple_voices": True,
            }
            features.update(volcengine_features)

        return features
