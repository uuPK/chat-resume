#!/usr/bin/env python3
"""
调试配置加载情况
"""

import os

# 确保在backend目录下
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 直接读取.env文件内容
print("=== 直接读取.env文件 ===")
with open(".env", "r") as f:
    for i, line in enumerate(f, 1):
        if "OPENROUTER" in line.upper():
            print(f"第{i}行: {line.strip()}")

print("\n=== 检查环境变量 ===")
for key in ["OPENROUTER_API_KEY", "OPENROUTER_API_BASE", "OPENROUTER_MODEL"]:
    value = os.getenv(key)
    print(f"{key}: {value}")

# 尝试手动模拟Pydantic加载
print("\n=== 模拟配置加载 ===")
env_vars = {}
with open(".env", "r") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            env_vars[key] = value

print(f"OPENROUTER_API_KEY: {env_vars.get('OPENROUTER_API_KEY', 'NOT_FOUND')}")
print(f"OPENROUTER_API_BASE: {env_vars.get('OPENROUTER_API_BASE', 'NOT_FOUND')}")
print(f"OPENROUTER_MODEL: {env_vars.get('OPENROUTER_MODEL', 'NOT_FOUND')}")

# 检查API密钥格式
api_key = env_vars.get("OPENROUTER_API_KEY", "")
if api_key:
    print("\nAPI密钥分析:")
    print(f"- 长度: {len(api_key)}")
    print(f"- 前缀: {api_key[:10]}...")
    print(f"- 是否为空: {not api_key.strip()}")
    print(f"- 是否包含空格: {' ' in api_key}")
else:
    print("\n❌ API密钥为空或未找到")
