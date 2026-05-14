#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
BACKEND_LOG="${ROOT_DIR}/backend.log"
FRONTEND_LOG="${ROOT_DIR}/frontend.log"
VERBOSE="${VERBOSE:-0}"

echo "Restarting Chat Resume local services..."

if [ ! -f "${ROOT_DIR}/backend.sh" ] || [ ! -f "${ROOT_DIR}/frontend.sh" ]; then
    echo "Error: run this script from the project root."
    exit 1
fi

stop_port() {
    local port="$1"
    local pids
    pids="$(lsof -ti "tcp:${port}" || true)"
    if [ -n "${pids}" ]; then
        echo "Stopping processes on port ${port}: ${pids}"
        kill ${pids} || true
        sleep 1
        pids="$(lsof -ti "tcp:${port}" || true)"
        if [ -n "${pids}" ]; then
            echo "Force stopping processes on port ${port}: ${pids}"
            kill -9 ${pids} || true
        fi
    fi
}

stop_port "${BACKEND_PORT}"
stop_port "${FRONTEND_PORT}"

filter_backend_logs() {
    if [ "${VERBOSE}" = "1" ]; then
        sed -u "s/^/[backend] /"
        return
    fi

    awk '
        /volcengine/ {
            print "[backend] " $0
            fflush()
            next
        }
        /ERROR|Error|Exception|Traceback|WARNING|WARN|Uvicorn running|Application startup complete|Started server process/ {
            print "[backend] " $0
            fflush()
            next
        }
        /"GET |"POST |"PUT |"PATCH |"DELETE / {
            print "[backend] " $0
            fflush()
            next
        }
    '
}

filter_frontend_logs() {
    if [ "${VERBOSE}" = "1" ]; then
        sed -u "s/^/[frontend] /"
        return
    fi

    awk '
        /前端开发服务器已就绪|前端热更新已完成/ {
            print "[frontend] " $0
            fflush()
            next
        }
        /error|Error|failed|Failed|warning|Warning|Ready in|Local:|启动前端服务|启动前端开发服务器|Compiled .* in|Compiled in|GET .* [0-9][0-9][0-9] in/ {
            print "[frontend] " $0
            fflush()
            next
        }
    '
}

echo "Starting backend on http://localhost:${BACKEND_PORT}"
(
    cd "${ROOT_DIR}"
    bash ./backend.sh
) 2>&1 | tee "${BACKEND_LOG}" | filter_backend_logs &
BACKEND_PID=$!

echo "Starting frontend on http://localhost:${FRONTEND_PORT}"
(
    cd "${ROOT_DIR}"
    bash ./frontend.sh
) 2>&1 | tee "${FRONTEND_LOG}" | filter_frontend_logs &
FRONTEND_PID=$!

echo "Backend PID: ${BACKEND_PID}  log: ${BACKEND_LOG}"
echo "Frontend PID: ${FRONTEND_PID} log: ${FRONTEND_LOG}"
echo "Set VERBOSE=1 ./restart.sh to show full terminal logs."

cleanup() {
    echo ""
    echo "Stopping local services..."
    kill "${BACKEND_PID}" "${FRONTEND_PID}" 2>/dev/null || true
    stop_port "${BACKEND_PORT}"
    stop_port "${FRONTEND_PORT}"
}

trap cleanup INT TERM EXIT

wait "${BACKEND_PID}" "${FRONTEND_PID}"
