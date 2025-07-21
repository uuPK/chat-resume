#!/usr/bin/env python3
"""
火山引擎ASR配置测试脚本
用于检查和诊断ASR配置问题
"""

import os
import sys
import asyncio
from dotenv import load_dotenv
from app.services.volcengine_bigmodel_asr_service import VolcEngineBigModelASRService

# 加载环境变量
load_dotenv()

async def test_asr_config():
    """测试ASR配置"""
    print("=== 火山引擎ASR配置测试 ===\n")
    
    # 1. 检查环境变量
    print("1. 检查环境变量配置...")
    required_vars = [
        'VOLCENGINE_APP_KEY',
        'VOLCENGINE_ACCESS_TOKEN'
    ]
    
    optional_vars = [
        'VOLCENGINE_ASR_RESOURCE_ID'
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"   ✅ {var}: {'*' * (len(value) - 4) + value[-4:]}")
        else:
            print(f"   ❌ {var}: 未设置")
            missing_vars.append(var)
    
    for var in optional_vars:
        value = os.getenv(var)
        if value:
            print(f"   ✅ {var}: {value}")
        else:
            print(f"   ⚠️ {var}: 未设置（将使用默认值）")
    
    if missing_vars:
        print(f"\n❌ 缺少必要的环境变量: {', '.join(missing_vars)}")
        print("请在 .env 文件中配置这些变量")
        return False
    
    # 2. 创建服务实例
    print("\n2. 创建ASR服务实例...")
    try:
        asr_service = VolcEngineBigModelASRService()
        print("   ✅ ASR服务实例创建成功")
    except Exception as e:
        print(f"   ❌ ASR服务实例创建失败: {e}")
        return False
    
    # 3. 检查配置
    print("\n3. 检查服务配置...")
    config_items = {
        'app_key': bool(asr_service.app_key),
        'access_token': bool(asr_service.access_token),
        'resource_id': asr_service.resource_id
    }
    
    for key, value in config_items.items():
        if key == 'resource_id':
            print(f"   ✅ {key}: {value}")
        else:
            status = "✅" if value else "❌"
            print(f"   {status} {key}: {'已配置' if value else '未配置'}")
    
    # 4. 测试音频格式信息
    print("\n4. 测试音频格式信息...")
    try:
        format_info = asr_service.get_audio_format_info()
        print("   ✅ 音频格式信息获取成功:")
        for key, value in format_info.items():
            print(f"      {key}: {value}")
    except Exception as e:
        print(f"   ❌ 音频格式信息获取失败: {e}")
        return False
    
    # 5. 测试服务信息
    print("\n5. 测试服务信息...")
    try:
        service_info = asr_service.get_service_info()
        print(f"   ✅ 服务信息获取成功:")
        print(f"      服务名称: {service_info.get('service_name')}")
        print(f"      版本: {service_info.get('version')}")
        print(f"      支持的模式: {service_info.get('supported_modes')}")
        print(f"      当前端点: {service_info.get('current_endpoint')}")
    except Exception as e:
        print(f"   ❌ 服务信息获取失败: {e}")
        return False
    
    # 6. 测试WebSocket连接（网络连接）
    print("\n6. 测试WebSocket连接（网络连接）...")
    try:
        websocket = await asr_service.create_websocket_connection('streaming_input')
        if websocket:
            print("   ✅ WebSocket连接创建成功")
            print(f"      连接状态: {websocket.state}")
            
            # 清理连接
            await websocket.close()
        else:
            print(f"   ❌ WebSocket连接创建失败")
            return False
    except Exception as e:
        error_msg = str(e)
        print(f"   ❌ WebSocket连接失败: {error_msg}")
        
        # 提供解决建议
        if "配置不完整" in error_msg:
            print("\n💡 解决建议:")
            print("   - 检查 .env 文件中的火山引擎配置")
            print("   - 确保所有必要的环境变量都已设置")
        elif "网络" in error_msg or "连接" in error_msg or "超时" in error_msg:
            print("\n💡 解决建议:")
            print("   - 检查网络连接")
            print("   - 确认火山引擎服务是否正常")
            print("   - 检查防火墙设置")
            print("   - 尝试使用VPN或代理")
        elif "权限" in error_msg or "认证" in error_msg or "401" in error_msg:
            print("\n💡 解决建议:")
            print("   - 检查API密钥是否正确")
            print("   - 确认账户是否有ASR服务权限")
            print("   - 检查APP KEY是否正确")
        
        return False
    
    # 7. 测试简单语音识别
    print("\n7. 测试简单语音识别...")
    try:
        # 生成测试音频数据（1秒静音）
        test_audio = bytes([0] * 32000)  # 16kHz * 2 bytes * 1 second
        
        result = await asr_service.simple_recognition(test_audio)
        if result.get("success"):
            print("   ✅ 简单语音识别测试成功")
            print(f"      识别结果: '{result.get('text', '')}'")
            print(f"      音频信息: {result.get('audio_info', {})}")
            print(f"      语音分句: {len(result.get('utterances', []))} 个")
        else:
            print(f"   ❌ 简单语音识别测试失败: {result.get('error')}")
            return False
    except Exception as e:
        print(f"   ❌ 简单语音识别测试失败: {e}")
        return False
    
    print("\n🎉 所有测试通过！火山引擎大模型流式语音识别配置正确")
    return True

if __name__ == "__main__":
    try:
        success = asyncio.run(test_asr_config())
        if success:
            print("\n✨ ASR服务已准备就绪，可以在面试系统中使用语音功能")
        else:
            print("\n❌ ASR服务配置存在问题，请根据上述建议进行修复")
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n测试被中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n测试执行失败: {e}")
        sys.exit(1)