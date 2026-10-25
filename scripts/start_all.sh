#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -f "data/flyguard.db" ]; then
  echo "[FlyGuard AI] No local SQLite database found. Running bootstrap pipeline..."
  .venv/bin/python backend/scripts/bootstrap_pipeline.py
fi

echo "[FlyGuard AI] Starting FastAPI backend on http://127.0.0.1:8000 ..."
.venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

trap "kill $BACKEND_PID 2>/dev/null || true" EXIT

echo "[FlyGuard AI] Starting React/Vite frontend on http://127.0.0.1:5173 ..."
npm run dev --prefix frontend -- --host 0.0.0.0 --port 5173

