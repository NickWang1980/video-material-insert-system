@echo off
rem ============================================================
rem heygem REST sidecar launcher
rem Mirrors 一键运行.bat env vars, but boots api_server (FastAPI)
rem on port 8383 instead of the Gradio UI on 7860.
rem ============================================================

cd /d %~dp0

rem --- Locate portable py39 -------------------------------------------------
rem Strategy:
rem   1) Local %~dp0\py39\python.exe (default — self-contained layout, ~13 GB
rem      portable Python 3.9 + torch CUDA + ffmpeg + site-packages)
rem   2) %HEYGEM_PY39_DIR%\python.exe (env var override for special cases:
rem      shared py39 across multiple checkouts, alternate disk, etc.)
set PY39_DIR=
if exist "%cd%\py39\python.exe" set PY39_DIR=%cd%\py39
if "%PY39_DIR%"=="" if defined HEYGEM_PY39_DIR if exist "%HEYGEM_PY39_DIR%\python.exe" set PY39_DIR=%HEYGEM_PY39_DIR%
if "%PY39_DIR%"=="" (
  echo.
  echo [heygem-api] ERROR: portable py39 not found.
  echo [heygem-api]   Tried: %cd%\py39\python.exe
  echo [heygem-api]   And:   %%HEYGEM_PY39_DIR%%\python.exe
  echo.
  echo [heygem-api] Fix options ^(pick one^):
  echo [heygem-api]   1^) Copy a portable py39 into this folder:
  echo [heygem-api]      robocopy "X:\path\to\heygem\py39" "%cd%\py39" /E /MT:16
  echo [heygem-api]   2^) Point env var to an existing portable py39:
  echo [heygem-api]      set HEYGEM_PY39_DIR=X:\path\to\heygem\py39
  echo [heygem-api]   Note: py39 is intentionally excluded from git (size ~13 GB).
  echo [heygem-api]         If you cloned via git submodule, you must bring py39
  echo [heygem-api]         in by one of the above methods.
  echo.
  pause
  exit /b 1
)
echo [heygem-api] using py39 from: %PY39_DIR%

SET PYTHON_PATH=%PY39_DIR%\
SET GRADIO_TEMP_DIR=%cd%\tmp\
rem overriding default python env vars so a system Python install doesn't interfere
SET PYTHONHOME=
SET PYTHONPATH=
SET PYTHONEXECUTABLE=%PYTHON_PATH%\python.exe
SET PYTHONWEXECUTABLE=%PYTHON_PATH%pythonw.exe
SET PYTHON_EXECUTABLE=%PYTHON_PATH%\python.exe
SET PYTHONW_EXECUTABLE=%PYTHON_PATH%pythonw.exe
SET PYTHON_BIN_PATH=%PYTHON_EXECUTABLE%
SET PYTHON_LIB_PATH=%PYTHON_PATH%\Lib\site-packages
set CU_PATH=%PYTHON_PATH%\Lib\site-packages\torch\lib
set cuda_PATH=%PYTHON_PATH%\Library\bin
SET FFMPEG_PATH=%PY39_DIR%\ffmpeg\bin
SET PATH=%PYTHON_PATH%;%PYTHON_PATH%\Scripts;%FFMPEG_PATH%;%CU_PATH%;%cuda_PATH%;%PATH%
set HF_ENDPOINT=https://hf-mirror.com
set HF_HOME=%CD%\hf_download
set TRANSFORMERS_CACHE=%CD%\tf_download
set XFORMERS_FORCE_DISABLE_TRITON=1
set PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512

rem --- one-time dep self-check ---
"%PYTHON_EXECUTABLE%" -c "import fastapi, uvicorn, multipart" 2>nul
if errorlevel 1 (
  echo [heygem-api] Missing fastapi/uvicorn/python-multipart in portable py39. Installing now...
  "%PYTHON_EXECUTABLE%" -m pip install --no-warn-script-location fastapi "uvicorn[standard]" python-multipart
  if errorlevel 1 (
    echo [heygem-api] pip install failed. Check proxy / network / pip index.
    pause
    exit /b 1
  )
)

echo [heygem-api] launching REST sidecar on http://0.0.0.0:8383 ...
"%PYTHON_EXECUTABLE%" -m uvicorn api_server:app --host 0.0.0.0 --port 8383
pause
