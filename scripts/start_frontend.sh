#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../frontend"

# Sentinel-based dependency check: not just `node_modules` existence, but
# whether all critical packages are actually installed. This catches the case
# where node_modules is stale after package.json adds new deps (e.g. TTS
# module added vue-i18n + jszip on top of an existing install).
need_install=0
if [ ! -d node_modules ]; then
  need_install=1
else
  for pkg in vue vue-router pinia element-plus axios vue-i18n jszip; do
    if [ ! -f "node_modules/${pkg}/package.json" ]; then
      need_install=1
      break
    fi
  done
fi

if [ "$need_install" -eq 1 ]; then
  echo "[start_frontend] 依赖缺失 — 正在 npm install ..."
  npm install
fi

npm run dev
