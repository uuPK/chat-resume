#!/usr/bin/env python3
"""
调试WebSocket消息格式的脚本
"""

import asyncio
import websockets
import struct
import uuid
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

async def debug_websocket():
    """调试WebSocket消息格式"""
    app_key = os.getenv('VOLCENGINE_APP_KEY')
    access_token = os.getenv('VOLCENGINE_ACCESS_TOKEN')
    resource_id = os.getenv('VOLCENGINE_ASR_RESOURCE_ID', 'volc.bigasr.sauc.duration')
    
    if not app_key or not access_token:
        print("❌ 环境变量配置不完整")
        return
    
    print("🔍 调试WebSocket消息格式")
    print("=" * 50)
    
    # WebSocket连接参数
    endpoint = 'wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_nostream'
    connect_id = str(uuid.uuid4())
    
    headers = {
        'X-Api-App-Key': str(app_key),
        'X-Api-Access-Key': str(access_token),
        'X-Api-Resource-Id': resource_id,
        'X-Api-Connect-Id': connect_id
    }
    
    try:
        # 建立WebSocket连接
        print(f"📡 连接到: {endpoint}")
        websocket = await websockets.connect(endpoint, additional_headers=headers)
        print("✅ WebSocket连接成功")
        
        # 创建简单的配置消息
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
        
        # 发送配置消息（不使用我们的复杂协议，先测试简单消息）
        import json
        config_json = json.dumps(config)
        print(f"📤 发送配置消息: {config_json[:100]}...")
        
        await websocket.send(config_json)
        
        # 读取响应
        print("📥 等待响应...")
        response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
        
        print(f"📋 响应类型: {type(response)}")
        print(f"📋 响应长度: {len(response)} bytes")
        
        if isinstance(response, bytes):
            print(f"📋 前20字节 (hex): {response[:20].hex()}")
            print(f"📋 前20字节 (原始): {response[:20]}")
            
            # 尝试解析前4字节作为头部
            if len(response) >= 4:
                header_bytes = response[:4]
                byte1, byte2, byte3, byte4 = struct.unpack('>BBBB', header_bytes)
                print(f"📋 头部解析:")
                print(f"   Byte 1: {byte1:08b} (0x{byte1:02x})")
                print(f"   Byte 2: {byte2:08b} (0x{byte2:02x})")
                print(f"   Byte 3: {byte3:08b} (0x{byte3:02x})")
                print(f"   Byte 4: {byte4:08b} (0x{byte4:02x})")
                
                # 解析协议版本和头部大小
                protocol_version = (byte1 >> 4) & 0x0F
                header_size = byte1 & 0x0F
                message_type = (byte2 >> 4) & 0x0F
                message_flags = byte2 & 0x0F
                
                print(f"   Protocol Version: {protocol_version}")
                print(f"   Header Size: {header_size}")
                print(f"   Message Type: {message_type}")
                print(f"   Message Flags: {message_flags}")
                
                # 计算实际头部大小
                actual_header_size = header_size * 4
                print(f"   Actual Header Size: {actual_header_size} bytes")
                
                # 读取payload大小
                if len(response) >= actual_header_size + 4:
                    payload_size_bytes = response[actual_header_size:actual_header_size+4]
                    payload_size = struct.unpack('>I', payload_size_bytes)[0]
                    print(f"   Payload Size: {payload_size} bytes")
                    
                    # 检查是否有完整的payload
                    expected_total_size = actual_header_size + 4 + payload_size
                    print(f"   Expected Total Size: {expected_total_size} bytes")
                    print(f"   Actual Message Size: {len(response)} bytes")
                    
                    if len(response) >= expected_total_size:
                        print("✅ 消息格式正确")
                        
                        # 提取payload
                        payload = response[actual_header_size+4:actual_header_size+4+payload_size]
                        print(f"   Payload (前100字节): {payload[:100]}")
                        
                        # 尝试解析JSON
                        try:
                            payload_json = json.loads(payload.decode('utf-8'))
                            print(f"   JSON解析成功: {payload_json}")
                        except:
                            print("   JSON解析失败，可能是压缩数据")
                    else:
                        print("❌ 消息不完整")
                        print(f"   缺少 {expected_total_size - len(response)} 字节")
        else:
            print(f"📋 文本响应: {response}")
        
        await websocket.close()
        
    except Exception as e:
        print(f"❌ 错误: {e}")

if __name__ == "__main__":
    asyncio.run(debug_websocket())