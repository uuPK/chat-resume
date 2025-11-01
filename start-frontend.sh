#!/bin/bash

# Chat Resume 前端启动脚本
echo "🚀 启动 Chat Resume 前端服务..."

# 检查是否在正确的目录
if [ ! -f "frontend/package.json" ]; then
    echo "❌ 错误: 请在项目根目录运行此脚本"
    exit 1
fi

# 进入前端目录
cd frontend

# 检查是否存在 .env.local 文件
if [ ! -f ".env.local" ]; then
    echo "📝 创建 .env.local 文件..."
    cp .env.example .env.local
    echo "✅ 已创建 .env.local 文件"
fi

# 检查 Node.js 环境
if ! command -v node &> /dev/null; then
    echo "❌ 错误: 未找到 Node.js，请先安装 Node.js 18+"
    exit 1
fi

# 检查 npm 环境
if ! command -v npm &> /dev/null; then
    echo "❌ 错误: 未找到 npm，请先安装 npm"
    exit 1
fi

# 检查 Node.js 版本
NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo "❌ 错误: Node.js 版本过低，需要 18+，当前版本: $(node -v)"
    exit 1
fi

# 检查是否已安装依赖
if [ ! -d "node_modules" ]; then
    echo "📦 安装依赖包..."
    npm install
fi

# 启动开发服务器
echo "🌟 启动前端开发服务器..."
echo "前端将在 http://localhost:3000 运行"
echo "按 Ctrl+C 停止服务"
echo ""

npm run dev