#!/usr/bin/env python3
"""
修复后的WebSocket调试脚本
"""

import asyncio
import websockets
import struct
import uuid
import os
import json
import gzip
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def create_protocol_message(message_type, message_flags, serialization, compression, payload, sequence=None):
    """创建符合火山引擎协议的消息"""
    # 协议版本和头部大小
    protocol_version = 0b0001
    header_size = 0b0001
    
    # 创建头部
    byte1 = (protocol_version << 4) | header_size
    byte2 = (message_type << 4) | message_flags
    byte3 = (serialization << 4) | compression
    byte4 = 0x00  # 保留字段
    
    header = struct.pack('>BBBB', byte1, byte2, byte3, byte4)
    
    # 压缩payload
    if compression == 0b0001:  # Gzip压缩
        payload = gzip.compress(payload)
    
    # 构建消息
    message = header
    
    # 添加序列号（如果需要）
    if sequence is not None:
        message += struct.pack('>I', sequence)
    
    # 添加payload大小和payload
    message += struct.pack('>I', len(payload))
    message += payload
    
    return message

async def debug_websocket_fixed():
    """调试修复后的WebSocket消息格式"""
    app_key = os.getenv('VOLCENGINE_APP_KEY')
    access_token = os.getenv('VOLCENGINE_ACCESS_TOKEN')
    resource_id = os.getenv('VOLCENGINE_ASR_RESOURCE_ID', 'volc.bigasr.sauc.duration')
    
    if not app_key or not access_token:
        print("❌ 环境变量配置不完整")
        return
    
    print("🔍 调试修复后的WebSocket消息格式")
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
        
        # 创建符合协议的消息
        config_json = json.dumps(config).encode('utf-8')
        protocol_message = create_protocol_message(
            message_type=0b0001,  # Full client request
            message_flags=0b0000,  # 无特殊标志
            serialization=0b0001,  # JSON
            compression=0b0001,    # Gzip压缩
            payload=config_json
        )
        
        print(f"📤 发送协议消息长度: {len(protocol_message)} bytes")
        print(f"📤 消息头部 (hex): {protocol_message[:8].hex()}")
        
        await websocket.send(protocol_message)
        
        # 读取响应
        print("📥 等待响应...")
        response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
        
        print(f"📋 响应类型: {type(response)}")
        print(f"📋 响应长度: {len(response)} bytes")
        
        if isinstance(response, bytes):
            print(f"📋 前20字节 (hex): {response[:20].hex()}")
            
            # 解析头部
            if len(response) >= 4:
                header_bytes = response[:4]
                byte1, byte2, byte3, byte4 = struct.unpack('>BBBB', header_bytes)
                
                protocol_version = (byte1 >> 4) & 0x0F
                header_size = byte1 & 0x0F
                message_type = (byte2 >> 4) & 0x0F
                message_flags = byte2 & 0x0F
                serialization = (byte3 >> 4) & 0x0F
                compression = byte3 & 0x0F
                
                print(f"📋 响应解析:")
                print(f"   Protocol Version: {protocol_version}")
                print(f"   Header Size: {header_size}")
                print(f"   Message Type: {message_type}")
                print(f"   Message Flags: {message_flags}")
                print(f"   Serialization: {serialization}")
                print(f"   Compression: {compression}")
                
                offset = 4
                actual_header_size = header_size * 4
                
                # 读取序列号（如果存在）
                sequence = None
                if message_flags in [0b0001, 0b0011]:  # 有序列号
                    if len(response) >= offset + 4:
                        sequence = struct.unpack('>I', response[offset:offset+4])[0]
                        print(f"   Sequence: {sequence}")
                        offset += 4
                
                # 如果是错误消息，还有错误码
                if message_type == 0b1111:  # 错误消息
                    if len(response) >= offset + 4:
                        error_code = struct.unpack('>I', response[offset:offset+4])[0]
                        print(f"   Error Code: {error_code} (0x{error_code:08x})")
                        offset += 4
                
                # 读取payload大小
                if len(response) >= offset + 4:
                    payload_size = struct.unpack('>I', response[offset:offset+4])[0]
                    print(f"   Payload Size: {payload_size} bytes")
                    offset += 4
                    
                    # 读取payload
                    if len(response) >= offset + payload_size:
                        payload = response[offset:offset+payload_size]
                        
                        # 解压缩
                        if compression == 0b0001:  # Gzip
                            try:
                                payload = gzip.decompress(payload)
                                print("   Payload解压缩成功")
                            except:
                                print("   Payload解压缩失败")
                        
                        # 解析JSON
                        if serialization == 0b0001:  # JSON
                            try:
                                payload_json = json.loads(payload.decode('utf-8'))
                                print(f"   JSON内容: {payload_json}")
                            except Exception as e:
                                print(f"   JSON解析失败: {e}")
                                print(f"   原始payload: {payload}")
                        else:
                            print(f"   原始payload: {payload}")
                        
                        if message_type == 0b1001:  # 成功响应
                            print("✅ 收到成功响应")
                        elif message_type == 0b1111:  # 错误响应
                            print("❌ 收到错误响应")
                        
                    else:
                        print(f"❌ Payload不完整，期望 {payload_size} bytes，实际 {len(response) - offset} bytes")
                else:
                    print("❌ 无法读取payload大小")
        
        await websocket.close()
        
    except Exception as e:
        print(f"❌ 错误: {e}")

if __name__ == "__main__":
    asyncio.run(debug_websocket_fixed())