#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
PROJECT_ROOT="$(pwd)"
PROJECT_BASENAME="$(basename "$PROJECT_ROOT")"

MODE="dev"
FORCE_CLEAN_FOREIGN=0
ABORT_ON_FOREIGN=0
WITH_HEYGEM=0
for arg in "$@"; do
  case "$arg" in
    --prod)                 MODE="prod" ;;
    --local)                MODE="dev" ;;
    --force-clean-foreign)  FORCE_CLEAN_FOREIGN=1 ;;
    --abort-on-foreign)     ABORT_ON_FOREIGN=1 ;;
    --with-heygem)          WITH_HEYGEM=1 ;;
  esac
done

# ─── 颜色 ────────────────────────────────────────────────────────────────────
if [ -t 1 ]; then
  C_GREEN="\033[32m"; C_YELLOW="\033[33m"; C_RED="\033[31m"
  C_CYAN="\033[36m";  C_BOLD="\033[1m";    C_RESET="\033[0m"
else
  C_GREEN=""; C_YELLOW=""; C_RED=""; C_CYAN=""; C_BOLD=""; C_RESET=""
fi

PFX="[start_all]"
log_info() { echo -e "${PFX} $*"; }
log_ok()   { echo -e "${PFX} ${C_GREEN}✅${C_RESET}  $*"; }
log_warn() { echo -e "${PFX} ${C_YELLOW}⚠️ ${C_RESET} $*"; }
log_fail() { echo -e "${PFX} ${C_RED}❌${C_RESET}  $*"; }
log_fix()  { echo -e "${PFX} ${C_CYAN}⨯${C_RESET}  $*"; }

# ─── Pre-flight: 端口归属分类 ───────────────────────────────────────────────
# 在 precheck.sh 强杀任何 8000/5173 占用前先做一次 audit。
# 分类：OURS / QWEN3TTS_STANDALONE / FOREIGN_OTHER
# 主项目占用：8000 (FastAPI backend) + 5173 (Vite frontend)
# 已知冲突源：5000 (Qwen3-TTS Flask 独立) / 8000 (Qwen3-TTS Gradio 独立)
_port_pids() {
  local port="$1"
  netstat -ano 2>/dev/null \
    | awk -v p=":${port}" '$1~/TCP|UDP/ && ($2~p" " || $2~p"$") {print $NF}' \
    | sort -u | grep -E '^[0-9]+$' || true
}

# Echo: PID|Name|Path|Cmdline (truncated). Empty if PID gone.
_pid_info() {
  local pid="$1"
  [ "$pid" = "0" ] && return
  if ! command -v powershell >/dev/null 2>&1; then
    echo "${pid}|unknown|unknown|unknown"
    return
  fi
  powershell -NonInteractive -Command "
    \$ErrorActionPreference='SilentlyContinue'
    \$p = Get-CimInstance Win32_Process -Filter \"ProcessId=${pid}\"
    if (-not \$p) { return }
    \$cmd = if (\$p.CommandLine) { \$p.CommandLine.Substring(0, [Math]::Min(180, \$p.CommandLine.Length)) } else { '' }
    Write-Output ('${pid}|' + \$p.Name + '|' + \$p.ExecutablePath + '|' + \$cmd)
  " 2>/dev/null | tr -d '\r' | head -1
}

# Classify a single PID. Echoes one of: OURS / QWEN3TTS / FOREIGN
_classify_pid() {
  local info="$1"
  local cmd path
  cmd="$(echo "$info" | awk -F'|' '{print $4}')"
  path="$(echo "$info" | awk -F'|' '{print $3}')"

  # OURS — strict match so a plain shell that happens to cd into the project
  # directory isn't accidentally classified as ours (and thus auto-killable).
  # Require PROJECT_BASENAME to appear adjacent to a path separator AND inside
  # one of our subdirs (.venv / node_modules / frontend / backend).
  case "$path" in
    *"\\${PROJECT_BASENAME}\\.venv\\"*|*"/${PROJECT_BASENAME}/.venv/"*) echo "OURS"; return ;;
    *"\\${PROJECT_BASENAME}\\node_modules\\"*|*"/${PROJECT_BASENAME}/node_modules/"*) echo "OURS"; return ;;
    *"\\${PROJECT_BASENAME}\\frontend\\"*|*"/${PROJECT_BASENAME}/frontend/"*) echo "OURS"; return ;;
    *"\\${PROJECT_BASENAME}\\backend\\"*|*"/${PROJECT_BASENAME}/backend/"*) echo "OURS"; return ;;
  esac
  # Cmdline signals — these are typical OURS markers when port 8000/5173 are
  # held; the QWEN3TTS / FOREIGN classifier below catches the alternatives.
  case "$cmd" in
    *"backend.main"*|*"uvicorn"*|*"vite"*|*"electron"*) echo "OURS"; return ;;
  esac

  # Qwen3-TTS standalone (Gradio :8000 or Flask :5000) — the source repo we pulled this module from
  case "$cmd" in
    *"Qwen3-TTS"*|*"qwen_tts"*|*"start_web.py"*|*"web_server.py"*) echo "QWEN3TTS"; return ;;
  esac
  case "$path" in
    *"Qwen3-TTS"*) echo "QWEN3TTS"; return ;;
  esac

  echo "FOREIGN"
}

PORT_8000_OWNERS=()   # array of "PID|class|name|cmd_short"
PORT_5173_OWNERS=()
PORT_5000_OWNERS=()
HAS_FOREIGN_ON_OURS=0
HAS_QWEN3TTS_CONFLICT=0

_survey_port() {
  local port="$1" __outvar="$2" mark_conflict_if_collide="$3"
  local pids
  pids=$(_port_pids "$port")
  [ -z "$pids" ] && return 0
  for pid in $pids; do
    [ "$pid" = "0" ] && continue
    local info klass name cmd
    info=$(_pid_info "$pid")
    [ -z "$info" ] && continue
    klass=$(_classify_pid "$info")
    name=$(echo "$info" | awk -F'|' '{print $2}')
    cmd=$(echo "$info" | awk -F'|' '{print $4}' | cut -c1-80)
    eval "${__outvar}+=(\"\${pid}|\${klass}|\${name}|\${cmd}\")"

    if [ "$mark_conflict_if_collide" = "1" ]; then
      [ "$klass" = "FOREIGN" ] && HAS_FOREIGN_ON_OURS=1
      [ "$klass" = "QWEN3TTS" ] && HAS_QWEN3TTS_CONFLICT=1
    fi
  done
}

echo ""
echo -e "${C_BOLD}${PFX} ============================================${C_RESET}"
echo -e "${C_BOLD}${PFX}  端口归属预检 (启动前 audit)${C_RESET}"
echo -e "${C_BOLD}${PFX} ============================================${C_RESET}"

_survey_port 8000 PORT_8000_OWNERS 1   # 主项目占用，碰撞要标
_survey_port 5173 PORT_5173_OWNERS 1   # 主项目占用，碰撞要标
_survey_port 5000 PORT_5000_OWNERS 0   # 不是主项目用的，仅信息提示

_print_owners() {
  local label="$1" port="$2"
  shift 2
  local owners=("$@")
  if [ ${#owners[@]} -eq 0 ]; then
    log_ok "端口 ${port} (${label}) — 空闲"
    return
  fi
  for o in "${owners[@]}"; do
    local pid klass name cmd
    pid=$(echo "$o" | awk -F'|' '{print $1}')
    klass=$(echo "$o" | awk -F'|' '{print $2}')
    name=$(echo "$o" | awk -F'|' '{print $3}')
    cmd=$(echo "$o" | awk -F'|' '{print $4}')
    case "$klass" in
      OURS)
        log_fix "端口 ${port} (${label}) — OURS  PID=${pid}  ${name}  → 将被自动清理"
        ;;
      QWEN3TTS)
        log_warn "端口 ${port} (${label}) — Qwen3-TTS standalone  PID=${pid}  ${name}"
        log_info "       cmd: ${cmd}"
        log_info "       建议: 先停掉独立项目  (cd D:/workspace/bzybox/v-project/Qwen3-TTS && ./stop_all.sh)"
        ;;
      FOREIGN)
        log_warn "端口 ${port} (${label}) — FOREIGN  PID=${pid}  ${name}"
        log_info "       cmd: ${cmd}"
        log_info "       建议: 关闭该进程  或  重启时加 --force-clean-foreign"
        ;;
    esac
  done
}

_print_owners "FastAPI backend"  8000 "${PORT_8000_OWNERS[@]:-}"
_print_owners "Vite frontend"    5173 "${PORT_5173_OWNERS[@]:-}"
_print_owners "Qwen3-TTS Flask?" 5000 "${PORT_5000_OWNERS[@]:-}"

# 处理外部冲突
if [ "$HAS_FOREIGN_ON_OURS" -eq 1 ] || [ "$HAS_QWEN3TTS_CONFLICT" -eq 1 ]; then
  if [ "$ABORT_ON_FOREIGN" -eq 1 ]; then
    log_fail "检测到外部进程占用主项目端口 — 因 --abort-on-foreign 中止启动"
    exit 1
  fi
  if [ "$FORCE_CLEAN_FOREIGN" -eq 1 ]; then
    log_warn "—— 用户传入 --force-clean-foreign，主动清理外部占用 ——"
    _kill_owners() {
      local owners=("$@")
      for o in "${owners[@]}"; do
        local pid klass
        pid=$(echo "$o" | awk -F'|' '{print $1}')
        klass=$(echo "$o" | awk -F'|' '{print $2}')
        [ "$klass" = "OURS" ] && continue
        if command -v taskkill >/dev/null 2>&1; then
          taskkill //F //PID "$pid" >/dev/null 2>&1 || true
        else
          kill -9 "$pid" 2>/dev/null || true
        fi
        log_fix "kill PID=${pid} (${klass})"
      done
    }
    _kill_owners "${PORT_8000_OWNERS[@]:-}"
    _kill_owners "${PORT_5173_OWNERS[@]:-}"
    sleep 1
  else
    log_info "—— 默认不杀外部进程；下一步 precheck.sh 的 free_port 仍会兜底强杀 ——"
    log_info "    要中止则按 Ctrl+C；要静默清理外部占用 重启时加 --force-clean-foreign"
    log_info "    要中止启动而不杀任何东西 加 --abort-on-foreign"
    sleep 2  # 给用户 2s 决策窗口
  fi
fi

echo ""
log_info "—— 调用 precheck.sh 走依赖/模型/数据库/端口正式预检 ——"

# 启动前预检（依赖、模型、端口、数据库）
./scripts/precheck.sh || exit 1

if [ "$MODE" = "prod" ]; then
  # Sentinel-based dep check (mirrors start_frontend.sh). Catches stale
  # node_modules missing TTS-era additions (vue-i18n / jszip).
  (
    cd frontend
    need_install=0
    if [ ! -d node_modules ]; then
      need_install=1
    else
      for pkg in vue vue-router pinia element-plus axios vue-i18n jszip; do
        [ -f "node_modules/${pkg}/package.json" ] || { need_install=1; break; }
      done
    fi
    [ "$need_install" -eq 1 ] && { log_info "frontend 依赖缺失 — npm install ..."; npm install; }
    npm run build
  )
  ./scripts/start_backend.sh --prod
  exit 0
fi

./scripts/start_backend.sh &
./scripts/start_frontend.sh &

# Optional: heygem 数字人 sidecar (vendor/heygem/start_api.bat on :8383)
if [ "$WITH_HEYGEM" -eq 1 ]; then
  if [ -x "vendor/heygem/start_api.bat" ] || [ -f "vendor/heygem/start_api.bat" ]; then
    log_info "—— 启动 heygem 数字人 sidecar (vendor/heygem/start_api.bat) ——"
    (cd vendor/heygem && cmd.exe /c start "heygem" cmd /k start_api.bat 2>/dev/null) || \
      log_warn "无法用 cmd.exe 启动 heygem，请手动双击 vendor/heygem/start_api.bat"
  else
    log_warn "--with-heygem 已指定，但 vendor/heygem/start_api.bat 不存在；请先 git submodule update --init"
  fi
fi

# Wait for frontend to be ready, then open login page
(sleep 6 && cmd.exe /c start "" "http://localhost:5173/login" 2>/dev/null || xdg-open "http://localhost:5173/login" 2>/dev/null || open "http://localhost:5173/login" 2>/dev/null) &

wait
