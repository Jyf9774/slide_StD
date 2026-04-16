#!/bin/bash
# StD Pipeline Dashboard - Start Script
# Starts both FastAPI backend and Vite dev server

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== StD Pipeline Dashboard ==="
echo ""

# Start backend
echo "[Backend] Starting FastAPI server on :8765 ..."
cd "$PROJECT_ROOT"
python3 web/server.py &
BACKEND_PID=$!

# Start frontend
echo "[Frontend] Starting Vite dev server on :5173 ..."
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
