@echo off
setlocal

cd /d %~dp0\..

set MODE=dev
set WITH_HEYGEM=0
:parse_args
if "%~1"=="" goto args_done
if "%~1"=="--prod" set MODE=prod
if "%~1"=="--with-heygem" set WITH_HEYGEM=1
shift
goto parse_args
:args_done

if "%MODE%"=="prod" (
  echo Building frontend...
  cd frontend
  REM Sentinel-based dep check (mirrors start_frontend.bat). Catches stale
  REM node_modules missing TTS-era additions (vue-i18n / jszip).
  set NEED_INSTALL=0
  if not exist node_modules set NEED_INSTALL=1
  if exist node_modules (
    for %%P in (vue vue-router pinia element-plus axios vue-i18n jszip) do (
      if not exist node_modules\%%P\package.json set NEED_INSTALL=1
    )
  )
  if "%NEED_INSTALL%"=="1" (
    echo Installing frontend dependencies...
    npm install
  )
  npm run build
  cd ..
  echo Starting backend ^(production static hosting^)...
  call scripts\start_backend.bat --prod
  exit /b 0
)

start "backend" cmd /k scripts\start_backend.bat
start "frontend" cmd /k scripts\start_frontend.bat

if "%WITH_HEYGEM%"=="1" (
  if exist vendor\heygem\start_api.bat (
    echo Starting heygem digital-human sidecar...
    start "heygem" cmd /k "cd /d %~dp0\..\vendor\heygem && start_api.bat"
  ) else (
    echo [WARN] --with-heygem requested but vendor\heygem\start_api.bat not found.
    echo        Run: git submodule update --init
  )
)

echo Started. Frontend: http://localhost:5173  Backend: http://localhost:8000
if "%WITH_HEYGEM%"=="1" echo            heygem:   http://localhost:8383
