"""
火山引擎端到端实时语音大模型服务
提供实时语音识别和语音合成功能
"""

import asyncio
import json
import base64
import websockets
import hashlib
import hmac
import time
from typing import Dict, Any, Optional, Callable, AsyncGenerator
from urllib.parse import urlencode
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class VolcEngineASRService:
    """火山引擎实时语音识别服务"""
    
    def __init__(self):
        self.access_key = getattr(settings, 'VOLCENGINE_ACCESS_KEY', None)
        self.secret_key = getattr(settings, 'VOLCENGINE_SECRET_KEY', None)
        self.region = getattr(settings, 'VOLCENGINE_REGION', 'cn-north-1')
        self.app_id = getattr(settings, 'VOLCENGINE_ASR_APP_ID', None)
        self.websocket_url = "wss://openspeech.bytedance.com/api/v1/sasr/realtime"
        
    def _generate_signature(self, query_params: Dict[str, str]) -> str:
        """生成API签名"""
        # 按字典序排序参数
        sorted_params = sorted(query_params.items())
        query_string = urlencode(sorted_params)
        
        # 构造签名字符串
        string_to_sign = f"GET\n/api/v1/sasr/realtime\n{query_string}"
        
        # 计算签名
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _get_websocket_url(self) -> str:
        """获取WebSocket连接URL"""
        if not self.access_key or not self.secret_key or not self.app_id:
            raise ValueError("火山引擎配置不完整")
        
        timestamp = str(int(time.time()))
        
        query_params = {
            'appid': self.app_id,
            'access_key': self.access_key,
            'timestamp': timestamp,
            'version': 'v1',
            'region': self.region,
            'format': 'pcm',
            'sample_rate': '16000',
            'channel': '1',
            'lang': 'zh-CN'
        }
        
        signature = self._generate_signature(query_params)
        query_params['signature'] = signature
        
        query_string = urlencode(query_params)
        return f"{self.websocket_url}?{query_string}"
    
    async def create_realtime_session(self) -> Dict[str, Any]:
        """创建实时语音识别会话"""
        try:
            # 检查配置
            if not all([self.access_key, self.secret_key, self.app_id]):
                raise ValueError("火山引擎配置不完整，请检查 VOLCENGINE_ACCESS_KEY、VOLCENGINE_SECRET_KEY、VOLCENGINE_ASR_APP_ID 环境变量")
            
            websocket_url = self._get_websocket_url()
            logger.info(f"正在连接火山引擎WebSocket: {websocket_url[:100]}...")
            
            # 连接WebSocket（设置超时）
            try:
                websocket = await asyncio.wait_for(
                    websockets.connect(websocket_url, ping_interval=None, ping_timeout=None),
                    timeout=10.0
                )
            except asyncio.TimeoutError:
                raise Exception("连接火山引擎WebSocket超时，请检查网络连接")
            except Exception as e:
                raise Exception(f"连接火山引擎WebSocket失败: {str(e)}")
            
            # 发送初始化消息
            init_message = {
                "signal": "start",
                "nbest": 1,
                "continuous_decoding": True,
                "show_utterances": True,
                "sequence": 1
            }
            
            await websocket.send(json.dumps(init_message))
            
            # 等待确认消息（设置超时）
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                result = json.loads(response)
            except asyncio.TimeoutError:
                await websocket.close()
                raise Exception("等待火山引擎确认消息超时")
            
            if result.get("code") == 0:
                logger.info("实时语音识别会话创建成功")
                return {
                    "success": True,
                    "websocket": websocket,
                    "session_id": result.get("sequence"),
                    "message": "实时语音识别会话创建成功"
                }
            else:
                await websocket.close()
                error_msg = result.get('message', f"错误代码: {result.get('code')}")
                raise Exception(f"火山引擎返回错误: {error_msg}")
                
        except Exception as e:
            logger.error(f"创建实时语音识别会话失败: {str(e)}")
            raise Exception(f"创建会话失败: {str(e)}")
    
    async def send_audio_chunk(self, websocket, audio_data: bytes, sequence: int) -> None:
        """发送音频数据块"""
        try:
            # 将音频数据编码为base64
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            
            message = {
                "signal": "audio",
                "audio": audio_base64,
                "sequence": sequence
            }
            
            await websocket.send(json.dumps(message))
            
        except Exception as e:
            logger.error(f"发送音频数据失败: {str(e)}")
            raise Exception(f"发送音频数据失败: {str(e)}")
    
    async def end_recognition(self, websocket, sequence: int) -> Dict[str, Any]:
        """结束语音识别"""
        try:
            end_message = {
                "signal": "end",
                "sequence": sequence
            }
            
            await websocket.send(json.dumps(end_message))
            
            # 等待最终结果
            response = await websocket.recv()
            result = json.loads(response)
            
            await websocket.close()
            
            return {
                "success": True,
                "final_result": result.get("result", ""),
                "message": "语音识别完成"
            }
            
        except Exception as e:
            logger.error(f"结束语音识别失败: {str(e)}")
            raise Exception(f"结束语音识别失败: {str(e)}")
    
    async def realtime_recognition_stream(
        self, 
        audio_stream: AsyncGenerator[bytes, None],
        on_partial_result: Optional[Callable[[str], None]] = None,
        on_final_result: Optional[Callable[[str], None]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """实时语音识别流处理"""
        websocket = None
        sequence = 1
        
        try:
            # 创建会话
            session = await self.create_realtime_session()
            websocket = session["websocket"]
            
            # 处理音频流
            async for audio_chunk in audio_stream:
                # 发送音频数据
                await self.send_audio_chunk(websocket, audio_chunk, sequence)
                sequence += 1
                
                # 尝试接收识别结果
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=0.1)
                    result = json.loads(response)
                    
                    if result.get("code") == 0:
                        text = result.get("result", "")
                        is_final = result.get("is_final", False)
                        
                        if is_final and on_final_result:
                            on_final_result(text)
                        elif not is_final and on_partial_result:
                            on_partial_result(text)
                        
                        yield {
                            "success": True,
                            "text": text,
                            "is_final": is_final,
                            "sequence": sequence
                        }
                        
                except asyncio.TimeoutError:
                    # 没有新的识别结果，继续处理
                    continue
                except Exception as e:
                    logger.error(f"接收识别结果失败: {str(e)}")
                    yield {
                        "success": False,
                        "error": str(e),
                        "sequence": sequence
                    }
            
            # 结束识别
            final_result = await self.end_recognition(websocket, sequence)
            yield final_result
            
        except Exception as e:
            logger.error(f"实时语音识别流处理失败: {str(e)}")
            if websocket:
                await websocket.close()
            yield {
                "success": False,
                "error": str(e),
                "sequence": sequence
            }
    
    async def simple_recognition(self, audio_data: bytes) -> Dict[str, Any]:
        """简单的一次性语音识别"""
        try:
            # 检查配置
            if not all([self.access_key, self.secret_key, self.app_id]):
                return {
                    "success": False,
                    "error": "火山引擎配置不完整，请检查环境变量配置",
                    "message": "语音识别失败：配置不完整"
                }
            
            # 检查音频数据
            if not audio_data or len(audio_data) == 0:
                return {
                    "success": False,
                    "error": "音频数据为空",
                    "message": "语音识别失败：无音频数据"
                }
            
            # 创建会话
            session = await self.create_realtime_session()
            websocket = session["websocket"]
            
            # 发送音频数据
            await self.send_audio_chunk(websocket, audio_data, 1)
            
            # 结束识别并获取结果
            result = await self.end_recognition(websocket, 2)
            
            return {
                "success": True,
                "text": result.get("final_result", ""),
                "message": "语音识别完成"
            }
            
        except Exception as e:
            logger.error(f"简单语音识别失败: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "语音识别失败"
            }
    
    def get_audio_format_info(self) -> Dict[str, Any]:
        """获取音频格式要求信息"""
        return {
            "format": "PCM",
            "sample_rate": 16000,
            "channels": 1,
            "bit_depth": 16,
            "byte_order": "little-endian",
            "encoding": "int16"
        }