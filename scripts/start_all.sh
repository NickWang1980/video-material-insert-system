#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

MODE="dev"
if [ "${1:-}" = "--prod" ]; then
  MODE="prod"
elif [ "${1:-}" = "--local" ]; then
  MODE="dev"
fi

if [ "$MODE" = "prod" ]; then
  (cd frontend && ([ -d node_modules ] || npm install) && npm run build)
  ./scripts/start_backend.sh --prod
  exit 0
fi

./scripts/start_backend.sh &
./scripts/start_frontend.sh &
wait
