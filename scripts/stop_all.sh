#!/usr/bin/env bash
# Stop all processes and services related to this project.
# Works on Windows (Git Bash / MSYS2) and Linux/Mac.

cd "$(dirname "$0")/.."
PROJECT_ROOT="$(pwd)"
PROJECT_BASENAME="$(basename "$PROJECT_ROOT")"
DB_FILE="$PROJECT_ROOT/data/database.db"

if [ -t 1 ]; then
  C_GREEN="\033[32m"; C_YELLOW="\033[33m"; C_RED="\033[31m"
  C_CYAN="\033[36m";  C_BOLD="\033[1m";    C_RESET="\033[0m"
else
  C_GREEN=""; C_YELLOW=""; C_RED=""; C_CYAN=""; C_BOLD=""; C_RESET=""
fi

PREFIX="[stop]"
echo -e "${C_BOLD}${PREFIX} 停止 video-material-insert-system 全部服务${C_RESET}"

# 全局：本次运行中常规权限杀不掉的 PID，最后会尝试 UAC 提权批量清理
STUBBORN_PIDS=()

# ── helpers ──────────────────────────────────────────────────────────────────

log_info() { echo -e "${PREFIX} $*"; }
log_ok()   { echo -e "${PREFIX} ${C_GREEN}✅${C_RESET}  $*"; }
log_warn() { echo -e "${PREFIX} ${C_YELLOW}⚠️ ${C_RESET} $*"; }
log_kill() { echo -e "${PREFIX} ${C_CYAN}⨯${C_RESET}  $*"; }
log_fail() { echo -e "${PREFIX} ${C_RED}❌${C_RESET}  $*"; }

pid_alive() {
  local pid="$1"
  [ -z "$pid" ] && return 1
  # PID 0 是 Windows System Idle Process / 内核占位，永远不算"活的可杀进程"
  [ "$pid" = "0" ] && return 1
  if command -v tasklist >/dev/null 2>&1; then
    tasklist //FI "PID eq ${pid}" 2>/dev/null | grep -q "[[:space:]]${pid}[[:space:]]"
  else
    kill -0 "$pid" 2>/dev/null
  fi
}

# 当前 shell 是否以管理员身份运行
_is_elevated_cache=""
is_elevated() {
  if [ -n "$_is_elevated_cache" ]; then
    [ "$_is_elevated_cache" = "1" ] && return 0 || return 1
  fi
  if ! command -v powershell >/dev/null 2>&1; then
    _is_elevated_cache="0"; return 1
  fi
  local res
  res=$(powershell -NonInteractive -Command "([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)" 2>/dev/null | tr -d '\r')
  if [ "$res" = "True" ]; then _is_elevated_cache="1"; return 0
  else _is_elevated_cache="0"; return 1
  fi
}

# 详细诊断一个不肯死的 PID：打印 Name / Path / Cmd / Owner
diagnose_pid() {
  local pid="$1"
  if ! command -v powershell >/dev/null 2>&1; then
    return 0
  fi
  local script
  script=$(cat <<PSEOF
\$ErrorActionPreference='SilentlyContinue'
\$p = Get-CimInstance Win32_Process -Filter "ProcessId=${pid}"
if (-not \$p) {
  Write-Output '    (进程已不存在 — 可能是 OS TCP 连接尚未回收的残留记录)'
  return
}
\$owner = (\$p | Invoke-CimMethod -MethodName GetOwner)
\$ownerStr = if (\$owner.User) { (\$owner.Domain + '\' + \$owner.User) } else { '<unknown>' }
\$cmd = if (\$p.CommandLine) { \$p.CommandLine.Substring(0, [Math]::Min(140, \$p.CommandLine.Length)) } else { '<no cmdline>' }
Write-Output ('    Name  : ' + \$p.Name)
Write-Output ('    Path  : ' + \$p.ExecutablePath)
Write-Output ('    Cmd   : ' + \$cmd)
Write-Output ('    Owner : ' + \$ownerStr)
PSEOF
)
  powershell -NonInteractive -Command "$script" 2>/dev/null | tr -d '\r'
}

# Robust kill: tries taskkill, then PowerShell Stop-Process, verifies after.
kill_pid() {
  local pid="$1" reason="${2:-}"
  [ -z "$pid" ] || [ "$pid" = "0" ] && return 0
  local label="PID=${pid}"
  [ -n "$reason" ] && label="${label}  ${reason}"

  # Path 1: taskkill /F
  if command -v taskkill >/dev/null 2>&1; then
    taskkill //F //PID "$pid" >/dev/null 2>&1 || true
  else
    kill -9 "$pid" 2>/dev/null || true
  fi
  sleep 0.3
  if ! pid_alive "$pid"; then
    log_kill "${label}"
    return 0
  fi

  # Path 2: PowerShell Stop-Process -Force (sometimes succeeds when taskkill silently fails)
  if command -v powershell >/dev/null 2>&1; then
    powershell -NonInteractive -Command "Stop-Process -Id ${pid} -Force -ErrorAction SilentlyContinue" 2>/dev/null || true
    sleep 0.5
  fi
  if ! pid_alive "$pid"; then
    log_kill "${label}  (via Stop-Process)"
    return 0
  fi

  log_fail "${label}  常规权限杀不掉 — 详情如下："
  diagnose_pid "$pid"
  # 收集起来，等所有端口都尝试过之后再批量 UAC 提权一次
  STUBBORN_PIDS+=("$pid")
  return 1
}

# 用 UAC 提权批量终止所有 STUBBORN_PIDS。会弹出一次 Windows 用户账户控制对话框。
# 成功则清空数组并返回 0，否则保留并返回 1。
elevated_kill_stubborn() {
  [ ${#STUBBORN_PIDS[@]} -eq 0 ] && return 0

  # 已是管理员还杀不掉 → 不是权限问题，提权也救不了
  if is_elevated; then
    log_warn "已是管理员仍杀不掉 PID=${STUBBORN_PIDS[*]} — 进程可能受 AV / EDR / 驱动保护"
    log_info "请用 Process Explorer / handle.exe 进一步排查"
    return 1
  fi
  if ! command -v powershell >/dev/null 2>&1; then
    log_fail "未找到 powershell，无法尝试提权"
    return 1
  fi

  log_info "—— 尝试以管理员权限批量终止顽固进程：${STUBBORN_PIDS[*]} ——"
  log_info "Windows 即将弹出"用户账户控制"对话框，请点 \"是\""

  # 把 kill 命令写入临时 .ps1，避免多层引号转义地狱
  local tmp_ps1="${TMPDIR:-/tmp}/stop_all_elevated_$$.ps1"
  local tmp_ps1_win
  tmp_ps1_win=$(cygpath -w "$tmp_ps1" 2>/dev/null || echo "$tmp_ps1")
  {
    echo '$ErrorActionPreference = "SilentlyContinue"'
    for p in "${STUBBORN_PIDS[@]}"; do
      echo "Stop-Process -Id ${p} -Force"
    done
    echo 'Start-Sleep -Milliseconds 800'
  } > "$tmp_ps1"

  # 提权运行，-Wait 让我们等它执行完毕
  powershell -NonInteractive -Command \
    "Start-Process powershell -Verb RunAs -Wait -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','${tmp_ps1_win}'" \
    2>/dev/null
  local rc=$?
  rm -f "$tmp_ps1"

  if [ $rc -ne 0 ]; then
    log_fail "提权失败（UAC 被拒绝或 Start-Process 出错）"
    return 1
  fi

  # 验证
  sleep 0.5
  local still_alive=()
  for p in "${STUBBORN_PIDS[@]}"; do
    pid_alive "$p" && still_alive+=("$p")
  done
  if [ ${#still_alive[@]} -eq 0 ]; then
    log_kill "已通过管理员权限终止：PID=${STUBBORN_PIDS[*]}"
    STUBBORN_PIDS=()
    return 0
  fi
  log_fail "提权后仍有未终止 PID=${still_alive[*]} — 可能受 AV / EDR 保护"
  STUBBORN_PIDS=("${still_alive[@]}")
  return 1
}

# Kill anything listening on the given TCP port.
free_port() {
  local port="$1"
  local pids
  pids=$(netstat -ano 2>/dev/null \
    | awk -v p=":${port}" '$1~/TCP|UDP/ && ($2~p" " || $2~p"$") {print $NF}' \
    | sort -u | grep -E '^[0-9]+$' || true)
  if [ -z "$pids" ]; then
    log_ok "端口 ${port} 已空闲"
    return 0
  fi
  for pid in $pids; do
    kill_pid "$pid" "占用端口 ${port}"
  done
}

# Kill processes by command-line keyword. Uses modern CIM (replaces WMIC).
# Args: $1 = process name (python.exe / node.exe), $2 = regex/keyword for command line.
kill_by_cmdline() {
  local proc_name="$1" keyword="$2"
  if ! command -v powershell >/dev/null 2>&1; then
    return 0
  fi
  local script
  script=$(cat <<PSEOF
\$found = 0
Get-CimInstance Win32_Process -Filter "Name='${proc_name}'" -ErrorAction SilentlyContinue |
  Where-Object { \$_.CommandLine -and \$_.CommandLine -match '${keyword}' } |
  ForEach-Object {
    Write-Output ("PID=" + \$_.ProcessId)
    Stop-Process -Id \$_.ProcessId -Force -ErrorAction SilentlyContinue
    \$found++
  }
if (\$found -eq 0) { Write-Output 'NONE' }
PSEOF
)
  local out
  out=$(powershell -NonInteractive -Command "$script" 2>/dev/null | tr -d '\r' || true)
  if [ "$out" = "NONE" ] || [ -z "$out" ]; then
    return 0
  fi
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    [ "$line" = "NONE" ] && continue
    local pid="${line#PID=}"
    log_kill "${proc_name}  ${line}  (匹配 ${keyword})"
  done <<<"$out"
}

# Detect whether the database file is currently exclusive-lockable (i.e., free).
db_is_free() {
  [ ! -f "$DB_FILE" ] && return 0
  if ! command -v powershell >/dev/null 2>&1; then
    return 0
  fi
  local db_win
  db_win=$(cygpath -w "$DB_FILE" 2>/dev/null || echo "$DB_FILE")
  local result
  result=$(powershell -NonInteractive -Command "
    try {
      \$s = [System.IO.File]::Open('${db_win}', 'Open', 'ReadWrite', 'None')
      \$s.Close(); Write-Output 'free'
    } catch { Write-Output 'locked' }
  " 2>/dev/null | tr -d '\r' || echo "unknown")
  [ "$result" = "free" ]
}

# Identify any process whose command line references this project — these are
# the most likely DB holders (uvicorn, vite, ASR worker threads).
list_project_holders() {
  if ! command -v powershell >/dev/null 2>&1; then
    return 0
  fi
  local script
  script=$(cat <<PSEOF
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
  Where-Object {
    \$_.Name -in @('python.exe','node.exe') -and
    \$_.CommandLine -and (
      \$_.CommandLine -match 'uvicorn' -or
      \$_.CommandLine -match 'backend\.main' -or
      \$_.CommandLine -match '${PROJECT_BASENAME}' -or
      \$_.CommandLine -match 'vite'
    )
  } |
  ForEach-Object {
    Write-Output ("PID=" + \$_.ProcessId + " | " + \$_.Name + " | " + \$_.CommandLine.Substring(0, [Math]::Min(120, \$_.CommandLine.Length)))
  }
PSEOF
)
  powershell -NonInteractive -Command "$script" 2>/dev/null | tr -d '\r'
}

# ── main ─────────────────────────────────────────────────────────────────────

log_info "—— 第 1 步：按命令行特征杀真凶（uvicorn / backend.main / vite）——"
kill_by_cmdline "python.exe" "uvicorn|backend\\.main"
kill_by_cmdline "node.exe"   "vite"

log_info "—— 第 2 步：清理项目目录残留 Python 进程 ——"
kill_by_cmdline "python.exe" "${PROJECT_BASENAME}"

log_info "—— 第 3 步：按端口兜底（清理任何遗留监听）——"
free_port 8000
free_port 5173

# 第 3.5 步：如果常规权限杀不掉，尝试 UAC 提权批量清理（弹一次 UAC）
elevated_kill_stubborn || true

# 等待 OS 释放句柄
sleep 1

log_info "—— 第 4 步：验证 database.db 锁状态 ——"
if db_is_free; then
  log_ok "database.db 未锁定"
else
  log_warn "database.db 仍被锁定，列出嫌疑进程："
  holders="$(list_project_holders)"
  if [ -z "$holders" ]; then
    log_fail "未能识别持锁进程；请手动用 Process Explorer / handle.exe 排查"
  else
    while IFS= read -r line; do
      [ -n "$line" ] && log_info "  ${line}"
    done <<<"$holders"
    log_info "再次强制清理..."
    kill_by_cmdline "python.exe" "uvicorn|backend\\.main|${PROJECT_BASENAME}"
    sleep 1
    if db_is_free; then
      log_ok "database.db 已释放"
    else
      log_fail "database.db 仍被锁定，请手动处理"
    fi
  fi
fi

log_info "—— 第 5 步：验证端口 ——"
for port in 8000 5173; do
  still=$(netstat -ano 2>/dev/null \
    | awk -v p=":${port}" '$1~/TCP|UDP/ && ($2~p" " || $2~p"$") {print $NF}' \
    | sort -u | grep -E '^[0-9]+$' || true)
  if [ -z "$still" ]; then
    log_ok "端口 ${port} 已释放"
    continue
  fi
  alive=""
  for pid in $still; do
    if pid_alive "$pid"; then alive="${alive} ${pid}"; fi
  done
  if [ -z "$alive" ]; then
    log_warn "端口 ${port} netstat 仍报 PID=$(echo $still | tr '\n' ' ')，但进程已不存在（OS TCP 残留，几秒后自动回收）"
  else
    log_fail "端口 ${port} 仍被活进程 PID=${alive# } 占用 — 详情如下："
    for p in $alive; do
      diagnose_pid "$p"
    done
  fi
done

echo -e "${C_BOLD}${PREFIX} 完成${C_RESET}"
