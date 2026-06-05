#!/bin/bash
# scripts/run_demo.sh
# Khởi động toàn bộ hệ thống demo:
#   1. FastAPI server
#   2. 3 workers (GAT, IDQN, Fixed) — mỗi cái 1 process
#   3. React dashboard
#
# Dùng: bash scripts/run_demo.sh
# Tắt:  Ctrl+C — tự kill tất cả process

set -e

PYTHON="python"
PID_FILE=".demo_pids"

# Cleanup khi tắt
cleanup() {
    echo ""
    echo "Đang dừng tất cả process..."
    if [ -f "$PID_FILE" ]; then
        while read -r pid; do
            kill "$pid" 2>/dev/null || true
        done < "$PID_FILE"
        rm "$PID_FILE"
    fi
    echo "Đã dừng."
    exit 0
}
trap cleanup SIGINT SIGTERM

echo "================================================"
echo "  Smart Traffic MARL — Live Demo"
echo "================================================"

> "$PID_FILE"  # Reset PID file

# 1. FastAPI server
echo ">>> Khởi động FastAPI server (port 8000)..."
$PYTHON -m server.main &
echo $! >> "$PID_FILE"
sleep 2

# 2. Workers
echo ">>> Khởi động Fixed-time worker (port 8815)..."
$PYTHON -m workers.worker_fixed &
echo $! >> "$PID_FILE"

echo ">>> Khởi động GAT-MARL worker (port 8813)..."
$PYTHON -m workers.worker_gat &
echo $! >> "$PID_FILE"

echo ">>> Khởi động IDQN worker (port 8814)..."
$PYTHON -m workers.worker_idqn &
echo $! >> "$PID_FILE"

sleep 1

# 3. Dashboard
echo ">>> Khởi động React dashboard (port 5173)..."
cd dashboard && npm run dev &
echo $! >> "$PID_FILE"
cd ..

echo ""
echo "================================================"
echo "  Dashboard: http://localhost:5173"
echo "  API:       http://localhost:8000"
echo "  Nhấn Ctrl+C để dừng tất cả"
echo "================================================"

# Giữ script chạy
wait