#!/bin/bash

# Chat Resume 后端重启脚本
set -euo pipefail

BACKEND_PORT="${BACKEND_PORT:-8000}"
BACKEND_LOG_FILE="${BACKEND_LOG_FILE:-logs/backend.log}"

# 本地默认保留结构化日志和 Agent trace。
export LOG_FORMAT="${LOG_FORMAT:-text}"
export AGENT_TRACE_LOG_ENABLED="${AGENT_TRACE_LOG_ENABLED:-true}"

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
    pids="$(
        { lsof -nP -ti "tcp:${port}" 2>/dev/null || true; } \
            | while read -r pid; do
                [ -n "${pid}" ] || continue
                command_line="$(ps -p "${pid}" -o command= 2>/dev/null || true)"
                if printf '%s\n' "${command_line}" \
                    | grep -Eq 'backend\.sh|uvicorn app\.main:app|chat-resume/backend'; then
                    echo "${pid}"
                fi
            done
    )"
    if [ -n "${pids}" ]; then
        echo "🛑 停止占用端口 ${port} 的进程: ${pids}"
        kill ${pids} || true
        sleep 1
        pids="$(
            echo "${pids}" \
                | while read -r pid; do
                    [ -n "${pid}" ] || continue
                    if kill -0 "${pid}" 2>/dev/null; then
                        echo "${pid}"
                    fi
                done
        )"
        if [ -n "${pids}" ]; then
            echo "🛑 强制停止占用端口 ${port} 的进程: ${pids}"
            kill -9 ${pids} || true
        fi
    fi
}

filter_terminal_logs() {
    if [ "${BACKEND_TERMINAL_VERBOSE:-0}" = "1" ]; then
        cat
        return
    fi

    awk '
        /^\{"timestamp":/ && /"message"[[:space:]]*:[[:space:]]*"app.ready"/ {
            print "✅ 后端应用已就绪 app.ready"
            fflush()
            next
        }
        /^\{"timestamp":/ && /"level"[[:space:]]*:[[:space:]]*"INFO"/ {
            next
        }
        {
            print
            fflush()
        }
    '
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
mkdir -p uploads logs
touch "${BACKEND_LOG_FILE}"

# 重启服务
stop_port "${BACKEND_PORT}"

echo "🌟 启动后端服务..."
echo "后端将在 http://localhost:${BACKEND_PORT} 运行"
echo "API 文档: http://localhost:${BACKEND_PORT}/docs"
echo "日志文件: backend/${BACKEND_LOG_FILE}"
echo "日志格式: ${LOG_FORMAT}; Agent trace: ${AGENT_TRACE_LOG_ENABLED}"
echo "终端默认隐藏 JSON INFO 日志，但会显示 app.ready；如需完整终端日志，设置 BACKEND_TERMINAL_VERBOSE=1。"
echo "按 Ctrl+C 停止服务"
echo ""

uv run uvicorn app.main:app --host 0.0.0.0 --port "${BACKEND_PORT}" --reload --reload-dir app 2>&1 | tee -a "${BACKEND_LOG_FILE}" | filter_terminal_logs
