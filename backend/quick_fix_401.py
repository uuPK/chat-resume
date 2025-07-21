#!/usr/bin/env python3
"""
快速修复401错误的诊断脚本
"""

import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def check_and_fix_401():
    """检查并修复401错误"""
    print("🔍 火山引擎ASR 401错误诊断")
    print("=" * 50)
    
    # 检查环境变量
    app_key = os.getenv('VOLCENGINE_APP_KEY')
    access_token = os.getenv('VOLCENGINE_ACCESS_TOKEN')
    resource_id = os.getenv('VOLCENGINE_ASR_RESOURCE_ID')
    
    print("\n1. 环境变量检查:")
    if not app_key or app_key == "请填入您的APP_ID":
        print("   ❌ VOLCENGINE_APP_KEY 未正确设置")
        print("   💡 请从火山引擎控制台获取您的APP ID")
        return False
    else:
        print(f"   ✅ VOLCENGINE_APP_KEY: {app_key}")
    
    if not access_token or access_token == "请填入您的ACCESS_TOKEN":
        print("   ❌ VOLCENGINE_ACCESS_TOKEN 未正确设置")
        print("   💡 请从火山引擎控制台获取您的Access Token")
        return False
    else:
        print(f"   ✅ VOLCENGINE_ACCESS_TOKEN: {access_token[:10]}...")
    
    print(f"   ✅ VOLCENGINE_ASR_RESOURCE_ID: {resource_id}")
    
    print("\n2. 401错误可能原因:")
    print("   • APP_KEY 或 ACCESS_TOKEN 不正确")
    print("   • 服务未开通或权限不足")
    print("   • 账户余额不足")
    print("   • 使用了错误的认证方式")
    
    print("\n3. 解决步骤:")
    print("   1️⃣ 访问火山引擎控制台：https://console.volcengine.com/")
    print("   2️⃣ 进入 语音技术 -> 大模型流式语音识别")
    print("   3️⃣ 确认服务已开通并有可用额度")
    print("   4️⃣ 获取正确的APP ID和Access Token")
    print("   5️⃣ 更新.env文件中的配置")
    
    print("\n4. 需要您手动完成的操作:")
    print("   📋 请按照以下步骤操作：")
    print("   1. 登录火山引擎控制台")
    print("   2. 开通大模型流式语音识别服务")
    print("   3. 获取正确的API凭证")
    print("   4. 更新.env文件")
    print("   5. 重新运行测试")
    
    print("\n5. 更新.env文件示例:")
    print("   VOLCENGINE_APP_KEY=您的实际APP_ID")
    print("   VOLCENGINE_ACCESS_TOKEN=您的实际ACCESS_TOKEN")
    print("   VOLCENGINE_ASR_RESOURCE_ID=volc.bigasr.sauc.duration")
    
    print("\n6. 完成配置后运行测试:")
    print("   python test_asr_config.py")
    
    return True

if __name__ == "__main__":
    check_and_fix_401()
    print("\n🎯 请按照上述步骤完成配置，然后重新测试语音识别功能。")