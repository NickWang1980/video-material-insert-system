#!/usr/bin/env bash
# precheck.sh — 环境预检脚本
# 检查并自动修复部署前置条件：工具链、依赖、ASR模型、端口、数据库
# 用法：./scripts/precheck.sh [--skip-asr]

set -uo pipefail

cd "$(dirname "$0")/.."
PROJECT_ROOT="$(pwd)"

SKIP_ASR=0
[ "${1:-}" = "--skip-asr" ] && SKIP_ASR=1

# ─── 颜色 ────────────────────────────────────────────────────────────────────
if [ -t 1 ]; then
  C_GREEN="\033[32m"; C_YELLOW="\033[33m"; C_RED="\033[31m"
  C_CYAN="\033[36m";  C_BOLD="\033[1m";    C_RESET="\033[0m"
else
  C_GREEN=""; C_YELLOW=""; C_RED=""; C_CYAN=""; C_BOLD=""; C_RESET=""
fi

PREFIX="[precheck]"
pass_count=0; fix_count=0; fail_count=0

log_ok()   { echo -e "${PREFIX} ${C_GREEN}✅${C_RESET}  $*";  pass_count=$((pass_count + 1)); }
log_warn() { echo -e "${PREFIX} ${C_YELLOW}⚠️ ${C_RESET} $*"; fix_count=$((fix_count + 1));  }
log_fail() { echo -e "${PREFIX} ${C_RED}❌${C_RESET}  $*";    fail_count=$((fail_count + 1)); }
log_dl()   { echo -e "${PREFIX} ${C_CYAN}⬇️ ${C_RESET} $*"; }
log_info() { echo -e "${PREFIX}      $*"; }

# ─── 读取 backend/.env ───────────────────────────────────────────────────────
load_env() {
  local env_file="$PROJECT_ROOT/backend/.env"
  [ -f "$env_file" ] || return 0
  while IFS= read -r line || [ -n "$line" ]; do
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ "$line" =~ ^[[:space:]]*$ ]] && continue
    local key="${line%%=*}"
    local val="${line#*=}"
    val="${val%%#*}"           # 去掉行内注释
    val="${val%"${val##*[![:space:]]}"}"   # 去尾部空白
    val="${val#"${val%%[![:space:]]*}"}"   # 去头部空白
    key="${key%"${key##*[![:space:]]}"}"
    key="${key#"${key%%[![:space:]]*}"}"
    [ -n "$key" ] && export "$key=$val" 2>/dev/null || true
  done < "$env_file"
}
load_env

FFMPEG_BIN="${FFMPEG_BIN:-./tools/ffmpeg/ffmpeg-8.1-essentials_build/bin/ffmpeg.exe}"
FFPROBE_BIN="${FFPROBE_BIN:-./tools/ffmpeg/ffmpeg-8.1-essentials_build/bin/ffprobe.exe}"

# 从 DATABASE_URL 中提取路径
DB_FILE="$PROJECT_ROOT/data/database.db"
if [ -n "${DATABASE_URL:-}" ]; then
  db_rel="${DATABASE_URL#sqlite:///}"
  db_rel="${db_rel#./}"
  DB_FILE="$PROJECT_ROOT/$db_rel"
fi

# ─── 辅助：激活 venv ─────────────────────────────────────────────────────────
_venv_activated=0
activate_venv() {
  [ "$_venv_activated" -eq 1 ] && return 0
  if [ -f "$PROJECT_ROOT/.venv/Scripts/activate" ]; then
    . "$PROJECT_ROOT/.venv/Scripts/activate" && _venv_activated=1
  elif [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
    . "$PROJECT_ROOT/.venv/bin/activate" && _venv_activated=1
  else
    return 1
  fi
}

# ─── 辅助：检查 ffmpeg/ffprobe 二进制 ───────────────────────────────────────
check_ffbin() {
  local label="$1" bin_path="$2"
  local abs_path="$bin_path"
  [[ "$bin_path" == ./* ]] && abs_path="${PROJECT_ROOT}/${bin_path#./}"

  local ver=""
  if [ -f "$abs_path" ]; then
    ver=$("$abs_path" -version 2>&1 | grep -oE 'version [0-9]+\.[0-9]+' | head -1 || true)
    log_ok "${label} ${ver} (${bin_path})"
  elif command -v "$(basename "$bin_path" .exe)" >/dev/null 2>&1; then
    local cmd
    cmd="$(basename "$bin_path" .exe)"
    ver=$("$cmd" -version 2>&1 | grep -oE 'version [0-9]+\.[0-9]+' | head -1 || true)
    log_ok "${label} ${ver} (系统 PATH)"
  else
    log_fail "${label} — 未找到: ${bin_path}"
    log_info "请检查 backend/.env 中的 FFMPEG_BIN / FFPROBE_BIN 路径"
  fi
}

# ─── 辅助：释放端口 ──────────────────────────────────────────────────────────
free_port() {
  local port="$1"
  local pids
  pids=$(netstat -ano 2>/dev/null \
    | awk -v p=":${port}" '$1~/TCP|UDP/ && ($2~p" " || $2~p"$") {print $NF}' \
    | sort -u | grep -E '^[0-9]+$' || true)

  if [ -z "$pids" ]; then
    log_ok "端口 ${port} — 空闲"
    return 0
  fi

  local killed=""
  for pid in $pids; do
    [ "$pid" = "0" ] && continue
    if command -v taskkill >/dev/null 2>&1; then
      taskkill /F /PID "$pid" >/dev/null 2>&1 || true
    else
      kill -9 "$pid" 2>/dev/null || true
    fi
    killed="${killed} PID=${pid}"
  done

  # 等待释放（最多 3 秒）
  local i=0
  while [ $i -lt 6 ]; do
    local still
    still=$(netstat -ano 2>/dev/null \
      | awk -v p=":${port}" '$1~/TCP|UDP/ && ($2~p" " || $2~p"$") {print $NF}' \
      | grep -E '^[0-9]+$' || true)
    [ -z "$still" ] && break
    sleep 0.5; i=$((i + 1))
  done

  local remaining
  remaining=$(netstat -ano 2>/dev/null \
    | awk -v p=":${port}" '$1~/TCP|UDP/ && ($2~p" " || $2~p"$") {print $NF}' \
    | grep -E '^[0-9]+$' || true)

  if [ -z "$remaining" ]; then
    log_warn "端口 ${port} — 已占用，已终止 (${killed# })，现已释放"
  else
    log_fail "端口 ${port} — 已占用，终止后仍未释放 (${killed# })"
  fi
}

# ─── 辅助：数据库锁检测 ──────────────────────────────────────────────────────
check_db_lock() {
  if [ ! -f "$DB_FILE" ]; then
    log_ok "数据库 — 文件不存在（首次启动，正常）"
    return 0
  fi

  local locked=0

  if command -v powershell >/dev/null 2>&1; then
    local db_win
    db_win=$(cygpath -w "$DB_FILE" 2>/dev/null || echo "$DB_FILE")
    local result
    result=$(powershell -NonInteractive -Command "
      try {
        \$s = [System.IO.File]::Open('${db_win}', 'Open', 'ReadWrite', 'None')
        \$s.Close(); Write-Output 'free'
      } catch { Write-Output 'locked' }
    " 2>/dev/null | tr -d '\r' || echo "unknown")
    [ "$result" = "locked" ] && locked=1
  elif command -v fuser >/dev/null 2>&1; then
    fuser "$DB_FILE" >/dev/null 2>&1 && locked=1 || true
  elif command -v lsof >/dev/null 2>&1; then
    lsof "$DB_FILE" >/dev/null 2>&1 && locked=1 || true
  fi

  if [ "$locked" -eq 0 ]; then
    log_ok "数据库 — 未锁定"
    return 0
  fi

  log_dl "数据库被锁定 — 尝试释放..."
  if command -v powershell >/dev/null 2>&1; then
    local proj_name
    proj_name="$(basename "$PROJECT_ROOT")"
    powershell -NonInteractive -Command "
      Get-WmiObject Win32_Process -Filter \"Name='python.exe'\" | ForEach-Object {
        if (\$_.CommandLine -match [regex]::Escape('${proj_name}')) {
          Stop-Process -Id \$_.ProcessId -Force -ErrorAction SilentlyContinue
        }
      }
    " 2>/dev/null || true
  elif command -v fuser >/dev/null 2>&1; then
    fuser -k "$DB_FILE" 2>/dev/null || true
  fi
  sleep 1
  log_warn "数据库 — 已尝试释放锁定进程"
}

# ─── 辅助：HF 缓存路径 ───────────────────────────────────────────────────────
get_hf_cache_dir() {
  [ -n "${HF_HUB_CACHE:-}" ] && echo "$HF_HUB_CACHE" && return
  local cache_home="${XDG_CACHE_HOME:-}"
  if [ -z "$cache_home" ]; then
    cache_home="$HOME/.cache"
  fi
  echo "${cache_home}/huggingface/hub"
}

asr_model_cached() {
  local model_name="$1"
  # 优先检查项目本地路径（无需 symlink 权限）
  local local_dir="$PROJECT_ROOT/data/asr_models/faster-whisper-${model_name}"
  [ -f "${local_dir}/model.bin" ] && return 0
  # 兼容：也检查 HF 缓存（旧版已缓存的情况）
  local hf_cache snap_base snap
  hf_cache="$(get_hf_cache_dir)"
  snap_base="${hf_cache}/models--Systran--faster-whisper-${model_name}/snapshots"
  [ -d "$snap_base" ] || return 1
  for snap in "${snap_base}"/*/; do
    [ -f "${snap}model.bin" ] && return 0
  done
  return 1
}

# ═════════════════════════════════════════════════════════════════════════════
echo ""
echo -e "${C_BOLD}${PREFIX} ============================================${C_RESET}"
echo -e "${C_BOLD}${PREFIX}  环境预检 — video-material-insert-system${C_RESET}"
echo -e "${C_BOLD}${PREFIX} ============================================${C_RESET}"

# ── 1. Python ─────────────────────────────────────────────────────────────────
PY_CMD=""
for cmd in python python3; do
  command -v "$cmd" >/dev/null 2>&1 && { PY_CMD="$cmd"; break; }
done

if [ -z "$PY_CMD" ]; then
  log_fail "Python — 未找到，请安装 Python 3.12+"
else
  PY_VER=$("$PY_CMD" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1)
  PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
  PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
  if [ "${PY_MAJOR:-0}" -ge 3 ] && [ "${PY_MINOR:-0}" -ge 12 ]; then
    log_ok "Python ${PY_VER}"
  else
    log_fail "Python ${PY_VER} — 需要 ≥ 3.12，请从 python.org 安装（非 Microsoft Store 版本）"
  fi
fi

# ── 2. Node.js + npm ──────────────────────────────────────────────────────────
if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
  log_ok "Node.js $(node --version 2>&1) / npm $(npm --version 2>&1)"
else
  log_fail "Node.js/npm — 未找到，请安装 Node.js 18+"
fi

# ── 3. .venv ──────────────────────────────────────────────────────────────────
if [ ! -d "$PROJECT_ROOT/.venv" ]; then
  if [ -n "$PY_CMD" ]; then
    log_dl ".venv 不存在 — 正在创建..."
    if "$PY_CMD" -m venv "$PROJECT_ROOT/.venv" 2>&1; then
      log_warn ".venv — 已创建"
    else
      log_fail ".venv — 创建失败，请手动运行: python -m venv .venv"
    fi
  else
    log_fail ".venv — 无法创建（Python 未找到）"
  fi
else
  log_ok ".venv 存在"
fi

# ── 4. Python 依赖 ────────────────────────────────────────────────────────────
if activate_venv 2>/dev/null; then
  missing=""
  for pkg in fastapi uvicorn faster-whisper opencc-python-reimplemented PyJWT bcrypt; do
    pip show "$pkg" >/dev/null 2>&1 || missing="$missing $pkg"
  done
  if [ -n "$missing" ]; then
    log_dl "Python 依赖缺失 (${missing# }) — 正在安装..."
    if pip install -r "$PROJECT_ROOT/backend/requirements.txt" -q 2>&1; then
      log_warn "Python 依赖 — 已安装"
    else
      log_fail "Python 依赖 — 安装失败，请手动运行: pip install -r backend/requirements.txt"
    fi
  else
    log_ok "Python 依赖已安装"
  fi
else
  log_warn ".venv 无法激活，跳过依赖检查"
fi

# ── 5. FFmpeg / FFprobe ───────────────────────────────────────────────────────
check_ffbin "FFmpeg " "$FFMPEG_BIN"
check_ffbin "FFprobe" "$FFPROBE_BIN"

# ── 6. ASR 模型（small + medium）─────────────────────────────────────────────
if [ "$SKIP_ASR" -eq 1 ]; then
  log_info "ASR 模型检查已跳过（--skip-asr）"
else
  for model in small medium; do
    if asr_model_cached "$model"; then
      log_ok "ASR 模型 ${model} — 就绪（已缓存）"
    else
      log_dl "ASR 模型 ${model} — 未找到，开始下载（small≈500MB，medium≈1.5GB）..."
      if activate_venv 2>/dev/null; then
        PYTHONUNBUFFERED=1 python - "$model" "$PROJECT_ROOT" <<'PYEOF'
import sys, os, shutil
model = sys.argv[1]
project_root = sys.argv[2]
local_dir = os.path.join(project_root, 'data', 'asr_models', f'faster-whisper-{model}')
os.makedirs(local_dir, exist_ok=True)
repo_id = f'Systran/faster-whisper-{model}'

def _do_download(repo_id, local_dir):
    from huggingface_hub import snapshot_download
    try:
        snapshot_download(repo_id=repo_id, local_dir=local_dir, local_dir_use_symlinks=False)
    except TypeError:
        # huggingface_hub >= 0.24 已移除该参数，local_dir 模式本身不创建 symlink
        snapshot_download(repo_id=repo_id, local_dir=local_dir)

print(f'[precheck]      仓库: {repo_id}', flush=True)
try:
    _do_download(repo_id, local_dir)
except OSError as e:
    if getattr(e, 'winerror', None) == 1314:
        # WinError 1314: 无符号链接权限 — 清除残留并强制以文件复制模式重试
        print('[precheck]      检测到 WinError 1314（Windows 无符号链接权限）', flush=True)
        print('[precheck]      正在自动切换为文件复制模式重试...', flush=True)
        shutil.rmtree(local_dir, ignore_errors=True)
        os.makedirs(local_dir, exist_ok=True)
        try:
            _do_download(repo_id, local_dir)
            print('[precheck]      已自动修复并重新下载完成', flush=True)
        except Exception as e2:
            print(f'[precheck]      重试失败: {e2}', file=sys.stderr, flush=True)
            print('[precheck]      永久修复方案：Windows 设置 → 隐私和安全性 → 开发者选项 → 开启「开发人员模式」', file=sys.stderr, flush=True)
            sys.exit(1)
    else:
        print(f'[precheck]      错误: {e}', file=sys.stderr, flush=True)
        sys.exit(1)
except Exception as e:
    print(f'[precheck]      错误: {e}', file=sys.stderr, flush=True)
    sys.exit(1)

print('[precheck]      验证模型完整性...', flush=True)
try:
    from faster_whisper import WhisperModel
    WhisperModel(local_dir, device='cpu', compute_type='int8')
except Exception as e:
    print(f'[precheck]      验证失败: {e}', file=sys.stderr, flush=True)
    sys.exit(1)
PYEOF
        py_exit=$?
        if [ $py_exit -eq 0 ]; then
          log_warn "ASR 模型 ${model} — 已下载并就绪"
        else
          log_fail "ASR 模型 ${model} — 下载失败"
          log_info "提示（中国大陆）：export HF_ENDPOINT=https://hf-mirror.com 后重试"
          log_info "提示（离线）：从工作机复制 ~/.cache/huggingface/hub/models--Systran--faster-whisper-${model}/"
        fi
      else
        log_fail "ASR 模型 ${model} — 无法下载（.venv 未就绪）"
      fi
    fi
  done
fi

# ── 7. 数据库锁 ───────────────────────────────────────────────────────────────
check_db_lock

# ── 8. 端口 8000 + 5173 ───────────────────────────────────────────────────────
free_port 8000
free_port 5173

# ═════════════════════════════════════════════════════════════════════════════
echo -e "${C_BOLD}${PREFIX} ============================================${C_RESET}"
if [ "$fail_count" -gt 0 ]; then
  echo -e "${PREFIX} ${C_BOLD}预检完成：${pass_count} 项通过，${fix_count} 项已自动修复，${C_RED}${fail_count} 项失败${C_RESET}"
  echo -e "${PREFIX} ${C_RED}请修复上述 ❌ 问题后再启动服务。${C_RESET}"
  echo -e "${C_BOLD}${PREFIX} ============================================${C_RESET}"
  echo ""
  exit 1
else
  echo -e "${PREFIX} ${C_BOLD}预检完成：${pass_count} 项通过，${fix_count} 项已自动修复，0 项失败 — 可以启动${C_RESET}"
  echo -e "${C_BOLD}${PREFIX} ============================================${C_RESET}"
  echo ""
fi
