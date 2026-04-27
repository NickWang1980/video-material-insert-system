#!/usr/bin/env bash
# Stop all processes and services related to this project.
# Works on Windows (Git Bash / MSYS2) and Linux/Mac.

cd "$(dirname "$0")/.."
PROJECT_ROOT="$(pwd)"
DB_FILE="$PROJECT_ROOT/data/database.db"

echo "[stop] Stopping video-material-insert-system services..."

# ── helpers ──────────────────────────────────────────────────────────────────

kill_pid() {
  local pid="$1"
  [ -z "$pid" ] || [ "$pid" = "0" ] && return
  if command -v taskkill >/dev/null 2>&1; then
    taskkill /F /PID "$pid" >/dev/null 2>&1 || true
  else
    kill -9 "$pid" 2>/dev/null || true
  fi
}

free_port() {
  local port="$1"
  local pids
  pids=$(netstat -ano 2>/dev/null \
    | awk -v p=":${port}" '$1~/TCP|UDP/ && ($2~p" " || $2~p"$") {print $NF}' \
    | sort -u | grep -E '^[0-9]+$' || true)
  if [ -z "$pids" ]; then
    echo "[stop] Port $port is already free."
    return 0
  fi
  for pid in $pids; do
    echo "[stop] Killing process on port $port (PID=$pid)"
    kill_pid "$pid"
  done
}

# Kill any Python process whose command line references this project root.
kill_project_python() {
  local found=0
  if command -v wmic >/dev/null 2>&1; then
    # Windows: query via WMIC
    local pids
    pids=$(wmic process where "Name='python.exe'" get ProcessId,CommandLine /format:csv 2>/dev/null \
      | grep -i "$(basename "$PROJECT_ROOT")" \
      | awk -F',' '{print $NF}' \
      | grep -E '^[0-9]+$' || true)
    for pid in $pids; do
      echo "[stop] Killing project Python process (PID=$pid)"
      kill_pid "$pid"
      found=1
    done
  else
    # Linux/Mac: use pgrep
    local pids
    pids=$(pgrep -f "$PROJECT_ROOT" 2>/dev/null || true)
    for pid in $pids; do
      echo "[stop] Killing project process (PID=$pid)"
      kill_pid "$pid"
      found=1
    done
  fi
  [ "$found" -eq 0 ] && echo "[stop] No project Python processes found."
}

# Release the SQLite database file on Windows by killing any process holding it.
free_database() {
  if [ ! -f "$DB_FILE" ]; then
    return 0
  fi
  # Try PowerShell to detect and kill the locking process
  if command -v powershell >/dev/null 2>&1; then
    powershell -NonInteractive -Command "
      \$db = '$DB_FILE'
      try {
        \$s = [System.IO.File]::Open(\$db, 'Open', 'ReadWrite', 'None')
        \$s.Close()
        Write-Output '[stop] database.db is free.'
      } catch {
        Write-Output '[stop] database.db is locked — finding holder...'
        Get-Process | ForEach-Object {
          \$p = \$_
          try {
            \$p.Modules | Where-Object { \$_.FileName -eq \$db } | ForEach-Object {
              Write-Output \"[stop] Killing PID \$(\$p.Id) (\$(\$p.ProcessName))\"
              Stop-Process -Id \$p.Id -Force
            }
          } catch {}
        }
        # Fallback: kill all python processes referencing this project
        Get-WmiObject Win32_Process -Filter \"Name='python.exe'\" | ForEach-Object {
          if (\$_.CommandLine -match [regex]::Escape('$(basename "$PROJECT_ROOT")')) {
            Write-Output \"[stop] Killing project Python PID \$(\$_.ProcessId)\"
            Stop-Process -Id \$_.ProcessId -Force -ErrorAction SilentlyContinue
          }
        }
      }
    " 2>/dev/null || true
  fi
}

# ── main ─────────────────────────────────────────────────────────────────────

# 1. Kill by port (backend + frontend dev server)
free_port 8000
free_port 5173

# 2. Kill any remaining project Python processes (uvicorn workers, forks, etc.)
kill_project_python

# 3. Release the database file if still locked
free_database

# 4. Short wait then verify
sleep 1

echo "[stop] Verifying ports..."
for port in 8000 5173; do
  still=$(netstat -ano 2>/dev/null \
    | awk -v p=":${port}" '$1~/TCP|UDP/ && ($2~p" " || $2~p"$") {print $NF}' \
    | grep -E '^[0-9]+$' || true)
  if [ -z "$still" ]; then
    echo "[stop] Port $port — OK (free)"
  else
    echo "[stop] WARNING: Port $port still in use by PID(s): $still"
  fi
done

echo "[stop] Done."
