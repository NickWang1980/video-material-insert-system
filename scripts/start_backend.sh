#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

MODE="dev"
if [ "${1:-}" = "--prod" ]; then
  MODE="prod"
fi

if [ ! -d ".venv" ]; then
  if command -v python >/dev/null 2>&1; then
    python -m venv .venv
  elif command -v python3 >/dev/null 2>&1; then
    python3 -m venv .venv
  else
    echo "ERROR: python/python3 not found in PATH"
    exit 1
  fi
fi

if [ -f ".venv/Scripts/activate" ]; then
  # Windows (Git Bash/MSYS)
  . .venv/Scripts/activate
elif [ -f ".venv/bin/activate" ]; then
  # macOS/Linux
  . .venv/bin/activate
else
  echo "ERROR: venv activation script not found under .venv/"
  exit 1
fi
python -m pip install -r backend/requirements.txt
if [ "$MODE" = "prod" ]; then
  python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
else
  # --reload-dir backend：仅监听 backend/ 源码变化
  # 避免 uvicorn 把整个项目（含 dist/ 编译产物、data/ 大文件）当成 watch target
  python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 \
    --reload --reload-dir backend
fi
