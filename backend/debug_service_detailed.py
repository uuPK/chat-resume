#!/usr/bin/env python3
"""
详细调试ASR服务的脚本
"""

import asyncio
import os
import sys
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

async def debug_service_detailed():
    """详细调试ASR服务"""
    print("🔍 详细调试ASR服务")
    print("=" * 50)
    
    # 创建服务实例
    try:
        service = VolcEngineBigModelASRService()
        print("✅ ASR服务实例创建成功")
    except Exception as e:
        print(f"❌ 创建服务实例失败: {e}")
        return
    
    # 创建测试音频数据
    print("\n📊 创建测试音频数据...")
    audio_data = create_test_audio_data()
    print(f"   音频数据长度: {len(audio_data)} bytes")
    
    # 测试WebSocket连接
    print("\n🔗 测试WebSocket连接...")
    try:
        websocket = await service.create_websocket_connection('streaming_input')
        print("✅ WebSocket连接成功")
        
        # 手动测试消息发送和接收
        print("\n📤 测试消息发送...")
        
        # 创建配置消息
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
        
        # 发送配置请求
        full_request = service._create_full_client_request(config)
        print(f"   发送配置消息长度: {len(full_request)} bytes")
        await websocket.send(full_request)
        
        # 读取配置响应
        print("\n📥 读取配置响应...")
        try:
            response = await service._read_message(websocket)
            print(f"   响应头部: {response['header']}")
            print(f"   响应payload: {response['payload']}")
            
            if response['header']['message_type'] == service.MSG_TYPE_ERROR:
                print("❌ 收到错误响应")
                return
            else:
                print("✅ 配置响应成功")
        except Exception as e:
            print(f"❌ 读取配置响应失败: {e}")
            return
        
        # 发送音频数据
        print("\n📤 发送音频数据...")
        audio_request = service._create_audio_request(audio_data, 1, is_last=True)
        print(f"   发送音频消息长度: {len(audio_request)} bytes")
        await websocket.send(audio_request)
        
        # 读取识别结果
        print("\n📥 读取识别结果...")
        try:
            result_response = await service._read_message(websocket)
            print(f"   结果头部: {result_response['header']}")
            print(f"   结果payload: {result_response['payload']}")
            
            if result_response['header']['message_type'] == service.MSG_TYPE_FULL_SERVER_RESPONSE:
                print("✅ 识别结果接收成功")
                payload = result_response['payload']
                if payload and 'result' in payload:
                    text = payload['result'].get('text', '')
                    print(f"   识别文本: '{text}'")
                    print(f"   音频信息: {payload.get('audio_info', {})}")
                else:
                    print("⚠️  结果payload为空或格式不正确")
            else:
                print("❌ 收到非预期的消息类型")
                
        except Exception as e:
            print(f"❌ 读取识别结果失败: {e}")
            import traceback
            traceback.print_exc()
        
        await websocket.close()
        
    except Exception as e:
        print(f"❌ WebSocket连接或通信失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 测试完整的simple_recognition方法
    print("\n🎯 测试完整的simple_recognition方法...")
    try:
        result = await service.simple_recognition(audio_data)
        print(f"   结果: {result}")
        
        if result['success']:
            print("✅ simple_recognition测试成功")
        else:
            print(f"❌ simple_recognition测试失败: {result['error']}")
            
    except Exception as e:
        print(f"❌ simple_recognition方法异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # 安装numpy如果需要
    try:
        import numpy as np
    except ImportError:
        print("❌ 需要安装numpy: pip install numpy")
        sys.exit(1)
    
    asyncio.run(debug_service_detailed())