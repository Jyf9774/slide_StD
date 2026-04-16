#!/bin/bash
# StD Pipeline Dashboard - Start Script
# Starts both FastAPI backend and Vite dev server

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

BACKEND_PORT=8765
FRONTEND_PORT=5173

echo "=== StD Pipeline Dashboard ==="
echo ""

# --- 检测并解除端口占用 ---
free_port() {
    local port=$1
    local name=$2
    local pids
    pids=$(lsof -ti :"$port" 2>/dev/null)
    if [ -n "$pids" ]; then
        echo "[Port] :$port ($name) 已被占用，正在释放..."
        for pid in $pids; do
            local cmd
            cmd=$(ps -p "$pid" -o comm= 2>/dev/null)
            echo "  -> kill PID $pid ($cmd)"
            kill "$pid" 2>/dev/null
        done
        sleep 1
        # 若仍未释放则强制终止
        pids=$(lsof -ti :"$port" 2>/dev/null)
        if [ -n "$pids" ]; then
            echo "  -> 强制终止残留进程..."
            kill -9 $pids 2>/dev/null
            sleep 0.5
        fi
        echo "[Port] :$port 已释放"
    else
        echo "[Port] :$port ($name) 可用"
    fi
}

free_port $BACKEND_PORT "Backend"
free_port $FRONTEND_PORT "Frontend"
echo ""

# Start backend
echo "[Backend] Starting FastAPI server on :$BACKEND_PORT ..."
cd "$PROJECT_ROOT"
python3 web/server.py &
BACKEND_PID=$!

# Start frontend
echo "[Frontend] Starting Vite dev server on :$FRONTEND_PORT ..."
cd "$SCRIPT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "  Backend:  http://localhost:8765"
echo "  Frontend: http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop both servers."

# Trap Ctrl+C
trap "echo ''; echo 'Shutting down...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM

wait
