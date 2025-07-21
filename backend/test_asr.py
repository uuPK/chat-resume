#!/usr/bin/env python3
"""
火山引擎ASR服务测试脚本
用于测试端到端实时语音大模型集成
"""

import asyncio
import sys
import os
import base64
sys.path.append('.')

from app.services.volcengine_bigmodel_asr_service import VolcEngineBigModelASRService
from app.core.config import settings

async def test_asr_service():
    """测试ASR服务"""
    print("开始测试火山引擎大模型流式语音识别服务...")
    
    # 检查配置
    asr_service = VolcEngineBigModelASRService()
    
    print("\n1. 检查配置状态...")
    config_status = {
        "app_key": "已配置" if asr_service.app_key else "未配置",
        "access_token": "已配置" if asr_service.access_token else "未配置", 
        "resource_id": asr_service.resource_id
    }
    
    for key, value in config_status.items():
        print(f"   {key}: {value}")
    
    if not all([asr_service.app_key, asr_service.access_token]):
        print("\n❌ 错误: 火山引擎配置不完整")
        print("请在 .env 文件中配置:")
        print("  VOLCENGINE_APP_KEY=your_app_key")
        print("  VOLCENGINE_ACCESS_TOKEN=your_access_token")
        print("  VOLCENGINE_ASR_RESOURCE_ID=volc.bigasr.sauc.duration")
        return False
    
    print("\n2. 获取音频格式信息...")
    try:
        format_info = asr_service.get_audio_format_info()
        print(f"✅ 音频格式要求:")
        for key, value in format_info.items():
            print(f"   {key}: {value}")
    except Exception as e:
        print(f"❌ 获取音频格式信息失败: {e}")
        return False
    
    print("\n3. 测试服务信息...")
    try:
        service_info = asr_service.get_service_info()
        print(f"✅ 服务信息获取成功")
        print(f"   服务名称: {service_info.get('service_name')}")
        print(f"   版本: {service_info.get('version')}")
        print(f"   支持的模式: {service_info.get('supported_modes')}")
        print(f"   当前端点: {service_info.get('current_endpoint')}")
    except Exception as e:
        print(f"❌ 服务信息获取失败: {e}")
        return False
    
    print("\n4. 测试WebSocket连接...")
    try:
        websocket = await asr_service.create_websocket_connection('streaming_input')
        if websocket:
            print(f"✅ WebSocket连接创建成功")
            print(f"   连接状态: {websocket.state}")
            
            # 关闭websocket连接
            await websocket.close()
        else:
            print(f"❌ WebSocket连接创建失败")
            return False
    except Exception as e:
        print(f"❌ WebSocket连接测试失败: {e}")
        return False
    
    print("\n5. 测试简单语音识别...")
    try:
        # 生成测试音频数据（1秒的静音PCM数据）
        test_audio_data = bytes([0] * 32000)  # 16kHz * 2 bytes * 1 second
        
        result = await asr_service.simple_recognition(test_audio_data)
        
        if result.get("success"):
            print(f"✅ 简单语音识别测试成功")
            print(f"   识别结果: '{result.get('text', '')}'")
            print(f"   音频信息: {result.get('audio_info', {})}")
            print(f"   语音分句: {len(result.get('utterances', []))} 个")
        else:
            print(f"❌ 简单语音识别失败: {result.get('error')}")
            return False
    except Exception as e:
        print(f"❌ 简单语音识别测试失败: {e}")
        return False
    
    print("\n🎉 所有测试通过！火山引擎大模型流式语音识别服务配置正确")
    return True

async def test_api_endpoints():
    """测试API端点"""
    print("\n开始测试API端点...")
    
    try:
        import httpx
        
        # 测试配置端点
        print("\n1. 测试配置端点...")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:8000/api/v1/asr/config",
                json={
                    "language": "zh-CN",
                    "sample_rate": 16000,
                    "format": "pcm",
                    "continuous": True
                },
                headers={"Authorization": "Bearer test_token"}
            )
            
            if response.status_code == 200:
                print("✅ 配置端点测试成功")
                config = response.json()
                print(f"   支持的语言: {config.get('config', {}).get('supported_languages', [])}")
            else:
                print(f"❌ 配置端点测试失败: {response.status_code}")
        
        # 测试状态端点
        print("\n2. 测试状态端点...")
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "http://localhost:8000/api/v1/asr/status",
                headers={"Authorization": "Bearer test_token"}
            )
            
            if response.status_code == 200:
                print("✅ 状态端点测试成功")
                status = response.json()
                print(f"   服务状态: {status.get('status')}")
            else:
                print(f"❌ 状态端点测试失败: {response.status_code}")
                
    except Exception as e:
        print(f"❌ API端点测试失败: {e}")
        return False
    
    return True

async def main():
    """主函数"""
    print("=== 火山引擎ASR服务测试 ===")
    
    # 测试服务
    service_ok = await test_asr_service()
    
    if service_ok:
        print("\n=== API端点测试 ===")
        # 注意：这需要后端服务运行
        # await test_api_endpoints()
    
    print("\n=== 测试完成 ===")
    return service_ok

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n测试被中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n测试执行失败: {e}")
        sys.exit(1)