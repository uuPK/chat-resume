#!/bin/bash

# Chat Resume 后端启动脚本
echo "🚀 启动 Chat Resume 后端服务..."

# 检查是否在正确的目录
if [ ! -f "backend/pyproject.toml" ]; then
    echo "❌ 错误: 请在项目根目录运行此脚本"
    exit 1
fi

# 进入后端目录
cd backend

# 检查是否存在 .env 文件
if [ ! -f ".env" ]; then
    echo "📝 创建 .env 文件..."
    cp .env.example .env
    echo "✅ 已创建 .env 文件，请根据需要修改配置"
fi

# 检查 Python 环境
if ! command -v uv &> /dev/null; then
    echo "❌ 错误: 未找到 uv，请先安装 uv"
    exit 1
fi

# 创建并同步虚拟环境
echo "📦 使用 uv 同步依赖..."
uv sync --extra dev

# 检查数据库
echo "🗄️ 初始化数据库..."
if [ ! -f "chat_resume.db" ]; then
    echo "创建数据库文件..."
fi

# 创建上传目录
mkdir -p uploads

# 启动服务
echo "🌟 启动后端服务..."
echo "后端将在 http://localhost:8000 运行"
echo "API 文档: http://localhost:8000/docs"
echo "按 Ctrl+C 停止服务"
echo ""

uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app
