#!/usr/bin/env python3
"""
测试API密钥是否有效
"""

import os
import httpx

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 从.env文件读取API密钥
api_key = ""
try:
    with open(".env", "r") as f:
        for line in f:
            if line.startswith("OPENROUTER_API_KEY"):
                api_key = line.split("=")[1].strip()
                break
except (FileNotFoundError, IOError):
    print("❌ 无法读取.env文件")
    exit(1)

if not api_key:
    print("❌ 未找到OPENROUTER_API_KEY")
    exit(1)

print(f"✅ 找到API密钥: {api_key[:20]}...")

# 测试API请求
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://chat-resume.com",
    "X-Title": "Chat Resume AI Assistant",
}

payload = {
    "model": "google/gemini-2.5-flash",
    "messages": [
        {"role": "user", "content": "Hello, please respond with just 'API working'"}
    ],
    "max_tokens": 10,
}

print("🔄 测试API请求...")

try:
    response = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        json=payload,
        headers=headers,
        timeout=10,
    )

    if response.status_code == 200:
        result = response.json()
        message = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        print(f"✅ API请求成功! 响应: {message}")
    else:
        print(f"❌ API请求失败: {response.status_code}")
        print(f"响应内容: {response.text}")

except Exception as e:
    print(f"❌ 请求异常: {e}")
