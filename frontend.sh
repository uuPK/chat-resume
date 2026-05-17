#!/bin/bash

# Chat Resume 前端重启脚本
if [ -z "${BASH_VERSION:-}" ]; then
    exec bash "$0" "$@"
fi

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
FRONTEND_LOG_FILE="${FRONTEND_LOG_FILE:-${ROOT_DIR}/frontend.log}"
FRONTEND_URL="http://localhost:${FRONTEND_PORT}"
FRONTEND_AUTO_OPEN="${FRONTEND_AUTO_OPEN:-1}"
export FORCE_COLOR="${FORCE_COLOR:-1}"

echo "🚀 重启 Chat Resume 前端服务..."

# 检查是否在正确的目录
if [ ! -f "frontend/package.json" ]; then
    echo "❌ 错误: 请在项目根目录运行此脚本"
    exit 1
fi

# 进入前端目录
cd "${ROOT_DIR}/frontend"

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

# 打开前端页面，优先使用 macOS open，兼容 Linux 桌面环境。
open_frontend_url() {
    local url="$1"

    if command -v open &> /dev/null; then
        open "${url}"
        return
    fi

    if command -v xdg-open &> /dev/null; then
        xdg-open "${url}"
        return
    fi

    return 1
}

# 等待开发服务器可访问后自动打开浏览器。
open_frontend_when_ready() {
    local url="$1"

    if [ "${FRONTEND_AUTO_OPEN}" != "1" ]; then
        return
    fi

    (
        for _ in {1..60}; do
            if curl -fsS --max-time 1 "${url}" > /dev/null 2>&1; then
                echo "🌐 在浏览器中打开 ${url}"
                open_frontend_url "${url}" > /dev/null 2>&1 || echo "⚠️ 无法自动打开浏览器，请手动访问 ${url}"
                return
            fi
            sleep 0.5
        done

        echo "⚠️ 前端服务启动后未能自动确认可访问，请手动访问 ${url}"
    ) &
}

filter_terminal_logs() {
    if [ "${FRONTEND_TERMINAL_VERBOSE:-0}" = "1" ]; then
        cat
        return
    fi

    awk '
        /Ready in/ {
            print "✅ 前端开发服务器已就绪 " $0
            fflush()
            next
        }
        /Compiled .* in|Compiled in|Compile ✓ Compiled in/ {
            print "✅ 前端热更新已完成 " $0
            fflush()
            next
        }
        {
            print
            fflush()
        }
    '
}

write_plain_log_and_stdout() {
    awk -v log_file="${FRONTEND_LOG_FILE}" '
        {
            raw = $0
            plain = raw
            gsub(/\033\[[0-9;?]*[ -\/]*[@-~]/, "", plain)
            print plain >> log_file
            fflush(log_file)
            print raw
            fflush()
        }
    '
}

# 检查是否已安装依赖
if [ ! -d "node_modules" ] || [ ! -x "node_modules/.bin/next" ]; then
    echo "📦 安装依赖包..."
    npm install
fi

# 重启开发服务器
stop_port "${FRONTEND_PORT}"

mkdir -p "$(dirname "${FRONTEND_LOG_FILE}")"
: > "${FRONTEND_LOG_FILE}"

echo "🌟 启动前端开发服务器..."
echo "前端将在 ${FRONTEND_URL} 运行"
echo "日志文件: ${FRONTEND_LOG_FILE}"
echo "终端彩色输出；日志文件保持无色纯文本。"
echo "终端会显示 Ready 和 Compiled 热更新完成提示；如需原始日志，设置 FRONTEND_TERMINAL_VERBOSE=1。"
echo "启动后会自动打开浏览器；如需关闭，设置 FRONTEND_AUTO_OPEN=0。"
echo "按 Ctrl+C 停止服务"
echo ""

open_frontend_when_ready "${FRONTEND_URL}"

npm run dev -- --port "${FRONTEND_PORT}" 2>&1 \
    | write_plain_log_and_stdout \
    | filter_terminal_logs
