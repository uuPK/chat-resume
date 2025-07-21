#!/usr/bin/env python3
"""
调试原始消息数据的脚本
"""

import asyncio
import os
import sys
import struct
import gzip
import json
import numpy as np
from dotenv import load_dotenv

# 添加项目根目录到路径
sys.path.insert(0, '/Users/psx849261680/Desktop/chat-resume/backend')

from app.services.volcengine_bigmodel_asr_service import VolcEngineBigModelASRService

# 加载环境变量
load_dotenv()

def create_test_audio_data():
    """创建测试音频数据 (16kHz, 1秒, 单声道PCM)"""
    sample_rate = 16000
    duration = 1.0  # 1秒
    frequency = 440  # 440Hz 音调
    
    # 生成正弦波
    t = np.linspace(0, duration, int(sample_rate * duration))
    sine_wave = np.sin(2 * np.pi * frequency * t)
    
    # 转换为16位PCM格式
    audio_data = (sine_wave * 32767).astype(np.int16).tobytes()
    
    return audio_data

def debug_raw_message_data(message_data: bytes, description: str):
    """调试原始消息数据"""
    print(f"\n🔍 {description}")
    print(f"   总长度: {len(message_data)} bytes")
    print(f"   前20字节 (hex): {message_data[:20].hex()}")
    
    if len(message_data) >= 4:
        # 解析头部
        header_bytes = message_data[:4]
        byte1, byte2, byte3, byte4 = struct.unpack('>BBBB', header_bytes)
        
        protocol_version = (byte1 >> 4) & 0x0F
        header_size = byte1 & 0x0F
        message_type = (byte2 >> 4) & 0x0F
        message_flags = byte2 & 0x0F
        serialization = (byte3 >> 4) & 0x0F
        compression = byte3 & 0x0F
        
        print(f"   Protocol Version: {protocol_version}")
        print(f"   Header Size: {header_size}")
        print(f"   Message Type: {message_type}")
        print(f"   Message Flags: {message_flags}")
        print(f"   Serialization: {serialization}")
        print(f"   Compression: {compression}")
        
        offset = 4
        actual_header_size = header_size * 4
        
        # 检查序列号
        sequence = None
        if message_flags in [0b0001, 0b0011]:  # 有序列号
            if len(message_data) >= offset + 4:
                sequence = struct.unpack('>I', message_data[offset:offset+4])[0]
                print(f"   Sequence: {sequence}")
                offset += 4
            else:
                print("   ❌ 序列号数据不完整")
                return
        
        # 检查错误码（如果是错误消息）
        if message_type == 0b1111:  # 错误消息
            if len(message_data) >= offset + 4:
                error_code = struct.unpack('>I', message_data[offset:offset+4])[0]
                print(f"   Error Code: {error_code} (0x{error_code:08x})")
                offset += 4
            else:
                print("   ❌ 错误码数据不完整")
                return
        
        # 读取payload大小
        if len(message_data) >= offset + 4:
            payload_size = struct.unpack('>I', message_data[offset:offset+4])[0]
            print(f"   Payload Size: {payload_size} bytes")
            offset += 4
            
            # 检查实际可用的payload数据
            available_payload = len(message_data) - offset
            print(f"   Available Payload: {available_payload} bytes")
            
            if available_payload >= payload_size:
                print("   ✅ Payload数据完整")
                
                payload = message_data[offset:offset+payload_size]
                
                # 解压缩
                if compression == 0b0001:  # Gzip
                    try:
                        payload = gzip.decompress(payload)
                        print("   ✅ Payload解压缩成功")
                    except Exception as e:
                        print(f"   ❌ Payload解压缩失败: {e}")
                        return
                
                # 解析JSON
                if serialization == 0b0001:  # JSON
                    try:
                        payload_json = json.loads(payload.decode('utf-8'))
                        print(f"   JSON内容: {payload_json}")
                    except Exception as e:
                        print(f"   ❌ JSON解析失败: {e}")
                        print(f"   原始payload前100字节: {payload[:100]}")
                else:
                    print(f"   原始payload前100字节: {payload[:100]}")
                    
            else:
                print(f"   ❌ Payload数据不完整，缺少 {payload_size - available_payload} bytes")
                print(f"   可能的原因:")
                print(f"     - WebSocket消息分片")
                print(f"     - 网络传输问题")
                print(f"     - 消息长度解析错误")
                
        else:
            print("   ❌ 无法读取payload大小")
    else:
        print("   ❌ 消息头部不完整")

async def debug_raw_message():
    """调试原始消息数据"""
    print("🔍 调试原始消息数据")
    print("=" * 50)
    
    # 创建服务实例
    service = VolcEngineBigModelASRService()
    
    # 创建测试音频数据
    audio_data = create_test_audio_data()
    print(f"📊 测试音频数据长度: {len(audio_data)} bytes")
    
    # 测试WebSocket连接
    try:
        websocket = await service.create_websocket_connection('streaming_input')
        print("✅ WebSocket连接成功")
        
        # 发送配置消息
        config = {
            "user": {"uid": "test_user"},
            "audio": {
                "format": "pcm",
                "codec": "raw",
                "rate": 16000,
                "bits": 16,
                "channel": 1
            },
            "request": {
                "model_name": "bigmodel",
                "enable_itn": True,
                "enable_punc": True,
                "enable_ddc": False,
                "show_utterances": True
            }
        }
        
        full_request = service._create_full_client_request(config)
        await websocket.send(full_request)
        
        # 读取配置响应
        config_response = await websocket.recv()
        debug_raw_message_data(config_response, "配置响应")
        
        # 发送音频数据
        audio_request = service._create_audio_request(audio_data, 2, is_last=True)
        await websocket.send(audio_request)
        
        # 读取识别结果（原始数据）
        try:
            result_response = await websocket.recv()
            debug_raw_message_data(result_response, "识别结果响应")
            
        except Exception as e:
            print(f"❌ 读取识别结果失败: {e}")
        
        await websocket.close()
        
    except Exception as e:
        print(f"❌ WebSocket通信失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_raw_message())