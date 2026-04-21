@echo off
setlocal

cd /d %~dp0\..

set MODE=dev
if "%1"=="--prod" set MODE=prod

if "%MODE%"=="prod" (
  echo Building frontend...
  cd frontend
  if not exist node_modules npm install
  npm run build
  cd ..
  echo Starting backend (production static hosting)...
  call scripts\start_backend.bat --prod
  exit /b 0
)

start "backend" cmd /k scripts\start_backend.bat
start "frontend" cmd /k scripts\start_frontend.bat

echo Started. Frontend: http://localhost:5173  Backend: http://localhost:8000
