@echo off
setlocal enabledelayedexpansion

cd /d %~dp0\..

set MODE=dev
if "%1"=="--prod" set MODE=prod

if not exist .venv (
  echo Creating venv...
  python -m venv .venv
)

echo Installing backend dependencies...
.venv\Scripts\python -m pip install -r backend\requirements.txt

echo Starting backend on http://localhost:8000 ...
if "%MODE%"=="prod" (
  .venv\Scripts\python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
) else (
  rem --reload-dir backend：仅监听 backend/ 源码变化，避免 dist/ 与 data/ 触发热重载
  .venv\Scripts\python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir backend
)
