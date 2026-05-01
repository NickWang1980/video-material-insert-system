#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

MODE="dev"
if [ "${1:-}" = "--prod" ]; then
  MODE="prod"
elif [ "${1:-}" = "--local" ]; then
  MODE="dev"
fi

# 启动前预检（依赖、模型、端口、数据库）
./scripts/precheck.sh || exit 1

if [ "$MODE" = "prod" ]; then
  (cd frontend && ([ -d node_modules ] || npm install) && npm run build)
  ./scripts/start_backend.sh --prod
  exit 0
fi

./scripts/start_backend.sh &
./scripts/start_frontend.sh &

# Wait for frontend to be ready, then open login page
(sleep 6 && cmd.exe /c start "" "http://localhost:5173/login" 2>/dev/null || xdg-open "http://localhost:5173/login" 2>/dev/null || open "http://localhost:5173/login" 2>/dev/null) &

wait
