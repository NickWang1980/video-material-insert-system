@echo off
setlocal

cd /d %~dp0\..\frontend

REM Sentinel-based dependency check (mirrors start_frontend.sh).
REM Stale node_modules from before TTS-module additions (vue-i18n / jszip)
REM would otherwise crash the Vite dev server on startup.
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

echo Starting frontend on http://localhost:5173 ...
npm run dev
