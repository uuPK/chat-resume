#!/bin/bash

# Chat Resume 后端重启脚本
set -euo pipefail

BACKEND_PORT="${BACKEND_PORT:-8000}"

echo "🚀 重启 Chat Resume 后端服务..."

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

stop_port() {
    local port="$1"
    local pids
    pids="$(lsof -ti "tcp:${port}" || true)"
    if [ -n "${pids}" ]; then
        echo "🛑 停止占用端口 ${port} 的进程: ${pids}"
        kill ${pids} || true
        sleep 1
        pids="$(lsof -ti "tcp:${port}" || true)"
        if [ -n "${pids}" ]; then
            echo "🛑 强制停止占用端口 ${port} 的进程: ${pids}"
            kill -9 ${pids} || true
        fi
    fi
}

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

# 重启服务
stop_port "${BACKEND_PORT}"

echo "🌟 启动后端服务..."
echo "后端将在 http://localhost:${BACKEND_PORT} 运行"
echo "API 文档: http://localhost:${BACKEND_PORT}/docs"
echo "按 Ctrl+C 停止服务"
echo ""

uv run uvicorn app.main:app --host 0.0.0.0 --port "${BACKEND_PORT}" --reload --reload-dir app
