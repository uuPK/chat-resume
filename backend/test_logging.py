#!/usr/bin/env python3
"""
测试日志配置是否正确工作
"""

import os
import sys
import logging

# 确保在backend目录下
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 模拟加载配置
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
if LOG_LEVEL == "None":  # 如果环境变量未设置，从.env文件读取
    try:
        with open('.env', 'r') as f:
            for line in f:
                if line.startswith('LOG_LEVEL'):
                    LOG_LEVEL = line.split('=')[1].strip()
                    break
    except:
        LOG_LEVEL = "INFO"

print(f"检测到的LOG_LEVEL: {LOG_LEVEL}")

# 配置日志
log_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
print(f"实际设置的日志等级: {logging.getLevelName(log_level)}")

logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger(__name__)

# 测试不同级别的日志
print("\n=== 测试不同级别的日志 ===")
logger.debug("这是一条DEBUG消息 - 如果你看到这条消息，说明DEBUG等级生效了")
logger.info("这是一条INFO消息")
logger.warning("这是一条WARNING消息")
logger.error("这是一条ERROR消息")

print(f"\n当前日志等级设置: {logging.getLevelName(logger.level)}")
print(f"DEBUG等级数值: {logging.DEBUG}")
print(f"当前logger等级数值: {logger.level}")
print(f"是否显示DEBUG: {logger.isEnabledFor(logging.DEBUG)}")