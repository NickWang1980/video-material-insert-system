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

# ─── 确保 backend/.env 存在 ──────────────────────────────────────────────────
ensure_env_file() {
  local env_file="$PROJECT_ROOT/backend/.env"
  local example_file="$PROJECT_ROOT/backend/.env.example"
  if [ ! -f "$env_file" ]; then
    if [ -f "$example_file" ]; then
      cp "$example_file" "$env_file"
      log_warn "backend/.env 不存在 — 已从 .env.example 创建"
    fi
  fi
}
ensure_env_file

# ─── .env 单键写入（保留其它行）──────────────────────────────────────────────
set_env_var() {
  local file="$1" key="$2" val="$3"
  [ -f "$file" ] || return 1
  if grep -qE "^[[:space:]]*${key}=" "$file" 2>/dev/null; then
    local tmp="${file}.precheck.tmp"
    awk -v k="$key" -v v="$val" '
      $0 ~ "^[[:space:]]*"k"=" { print k"="v; next }
      { print }
    ' "$file" > "$tmp" && mv "$tmp" "$file"
  else
    [ -s "$file" ] && [ -n "$(tail -c1 "$file" 2>/dev/null)" ] && printf '\n' >> "$file"
    printf '%s=%s\n' "$key" "$val" >> "$file"
  fi
}

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

# 完整性校验：模型目录必须满足
#   1) model.bin 存在且 ≥ 1 MB（过滤 0 字节占位 / 截断下载）
#   2) config.json 存在且非空
#   3) tokenizer.json / vocabulary.txt / vocab.json 三选一非空
_verify_asr_model_dir() {
  local d="$1"
  [ -d "$d" ] || return 1
  [ -f "${d}/model.bin" ] || return 1
  local size
  size=$(wc -c < "${d}/model.bin" 2>/dev/null || echo 0)
  [ "$size" -ge 1048576 ] || return 1
  [ -s "${d}/config.json" ] || return 1
  if [ -s "${d}/tokenizer.json" ] || [ -s "${d}/vocabulary.txt" ] || [ -s "${d}/vocab.json" ]; then
    return 0
  fi
  return 1
}

asr_model_cached() {
  local model_name="$1"
  # 优先检查项目本地路径（无需 symlink 权限）
  local local_dir="$PROJECT_ROOT/data/asr_models/faster-whisper-${model_name}"
  _verify_asr_model_dir "$local_dir" && return 0
  # 兼容：也检查 HF 缓存（旧版已缓存的情况）
  local hf_cache snap_base snap
  hf_cache="$(get_hf_cache_dir)"
  snap_base="${hf_cache}/models--Systran--faster-whisper-${model_name}/snapshots"
  [ -d "$snap_base" ] || return 1
  for snap in "${snap_base}"/*/; do
    _verify_asr_model_dir "${snap%/}" && return 0
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

# ── 2.5 CUDA Toolkit 检查（ASR CUDA 加速依赖）────────────────────────────────
check_cuda_compatibility() {
  if [ "$OS" != "Windows_NT" ]; then
    return 0
  fi
  local gpu_name
  gpu_name=$(powershell -Command "Get-WmiObject Win32_VideoController | Select-Object -ExpandProperty Name" 2>/dev/null | head -1 || true)
  if [ -z "$gpu_name" ]; then
    log_warn "无法检测 GPU 型号"
    return 0
  fi
  local compute_capability="unknown"
  case "$gpu_name" in
    *"RTX 50"*) compute_capability="9.0" ;;
    *"RTX 40"*) compute_capability="8.9" ;;
    *"RTX 30"*) compute_capability="8.6" ;;
    *"RTX 20"*) compute_capability="7.5" ;;
    *"GTX 16"*) compute_capability="7.5" ;;
    *"GTX 10"*) compute_capability="6.1" ;;
  esac

  log_info "检测到 GPU: ${gpu_name} (Compute Capability: ${compute_capability})"

  if [ "$compute_capability" = "unknown" ]; then
    log_warn "无法确定 GPU 计算能力"
    return 0
  fi

  local cuda_ver
  if command -v nvcc >/dev/null 2>&1; then
    cuda_ver=$(nvcc --version 2>/dev/null | grep -oE 'release [0-9]+\.[0-9]+' | head -1 | grep -oE '[0-9]+\.[0-9]+' || true)
  elif [ -n "${CUDA_PATH:-}" ] && [ -f "${CUDA_PATH}/bin/nvcc.exe" ]; then
    cuda_ver=$("${CUDA_PATH}/bin/nvcc.exe" --version 2>/dev/null | grep -oE 'release [0-9]+\.[0-9]+' | head -1 | grep -oE '[0-9]+\.[0-9]+' || true)
  fi

  if [ -z "$cuda_ver" ]; then
    log_warn "无法检测 CUDA 版本"
    return 0
  fi

  local cuda_major
  cuda_major=$(echo "$cuda_ver" | cut -d. -f1)

  case "$compute_capability" in
    9.0)
      if [ "$cuda_major" -lt 13 ]; then
        log_fail "CUDA ${cuda_ver} 不支持 Compute Capability 9.0 (RTX 50 系列)"
        log_info "需要 CUDA 13.x 以上版本"
        return 1
      fi
      ;;
    8.9)
      if [ "$cuda_major" -lt 12 ]; then
        log_fail "CUDA ${cuda_ver} 不支持 Compute Capability 8.9 (RTX 40 系列)"
        log_info "需要 CUDA 12.x 以上版本"
        return 1
      fi
      ;;
    8.6|7.5|6.1)
      if [ "$cuda_major" -gt 12 ]; then
        log_warn "CUDA ${cuda_ver} 可能不完全支持 Compute Capability ${compute_capability}"
      fi
      ;;
  esac

  log_ok "CUDA ${cuda_ver} 与 GPU 兼容"
  return 0
}

check_cuda_toolkit() {
  if [ "$OS" != "Windows_NT" ]; then
    return 0
  fi
  if command -v nvcc >/dev/null 2>&1; then
    local cuda_ver
    cuda_ver=$(nvcc --version 2>/dev/null | grep -oE 'release [0-9]+\.[0-9]+' | head -1 || true)
    log_ok "CUDA Toolkit ${cuda_ver} — 已安装（nvcc）"
    return 0
  fi
  if [ -n "${CUDA_PATH:-}" ] && [ -d "$CUDA_PATH" ]; then
    log_ok "CUDA Toolkit — 已安装（CUDA_PATH=${CUDA_PATH}）"
    return 0
  fi
  local default_cuda_path="C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA"
  if [ -d "$default_cuda_path" ]; then
    local latest_cuda
    latest_cuda=$(ls -td "$default_cuda_path"/v* 2>/dev/null | head -1 || true)
    if [ -n "$latest_cuda" ] && [ -f "${latest_cuda}/bin/nvcc.exe" ]; then
      log_ok "CUDA Toolkit — 已安装（${latest_cuda}）"
      return 0
    fi
  fi
  return 1
}

check_cuda_dlls() {
  if [ "$OS" != "Windows_NT" ]; then
    return 0
  fi
  # 用 Python 的 ctypes + glob 通配匹配 CUDA 12.x 运行时 DLL（兼容 cudart64_12.dll / cudart64_120.dll /
  # cudart64_125.dll 等不同副号），任一加载成功即视为可用；并附带打印
  #   ctranslate2.get_cuda_device_count() 与 torch.cuda.is_available()
  # 以便定位"装了 NVIDIA 驱动但未装 CUDA Toolkit / cuDNN"的 ASR float16 启动期假阳性。
  if [ -z "${PY_CMD:-}" ]; then
    return 1
  fi
  local extra_dirs=""
  if [ -n "${CUDA_PATH:-}" ]; then
    extra_dirs="${CUDA_PATH}/bin;${CUDA_PATH}/bin/x64"
  fi
  local output exit_code
  output=$(EXTRA_CUDA_DIRS="$extra_dirs" "$PY_CMD" - <<'PYEOF' 2>&1
import ctypes
import glob
import os
import sys

def _posix_to_win(p):
    # 把 Git Bash 的 /c/Windows/System32 形式转回 C:\Windows\System32
    # 仅当形如 /<letter>/... 时才转换，避免误伤合法 Windows 路径
    if p and len(p) > 2 and p[0] == "/" and p[2] == "/" and p[1].isalpha():
        return p[1].upper() + ":" + p[2:].replace("/", "\\")
    return p

def search_dirs():
    dirs = []
    raw_path = os.environ.get("PATH", "")
    # 兼容 Git Bash 的 POSIX PATH（: 分隔）与 cmd/PowerShell 的 Windows PATH（; 分隔）。
    # Git Bash 下 sys.platform == "win32" 时 os.pathsep == ";"，
    # 但 os.environ["PATH"] 仍是 :-分隔的 POSIX 串，直接 split(os.pathsep) 会得到一整条不分。
    if raw_path:
        chosen_sep = None
        for sep in (os.pathsep, ";", ":"):
            if sep and sep in raw_path:
                chosen_sep = sep
                break
        if chosen_sep is None:
            dirs.append(raw_path)
        else:
            dirs.extend(raw_path.split(chosen_sep))
    extra = os.environ.get("EXTRA_CUDA_DIRS", "")
    if extra:
        for d in extra.split(";"):
            d = d.strip()
            if d:
                dirs.append(d)
    seen, out = set(), []
    for d in dirs:
        if not d:
            continue
        d = _posix_to_win(d.strip())
        try:
            key = os.path.normcase(os.path.normpath(d))
        except Exception:
            key = d
        if key in seen:
            continue
        seen.add(key)
        out.append(d)
    return out

def find_dlls(pattern):
    found = []
    for d in search_dirs():
        try:
            found.extend(glob.glob(os.path.join(d, pattern)))
        except Exception:
            pass
    return found

def try_load_any(pattern):
    for p in find_dlls(pattern):
        try:
            p_norm = os.path.normpath(_posix_to_win(p))
            try:
                p_norm = os.path.realpath(p_norm)
            except Exception:
                pass
            ctypes.WinDLL(p_norm)
            return p_norm
        except OSError:
            continue
    return None

checks = {
    "cudart":   "cudart64_12*.dll",
    "cublas":   "cublas64_12*.dll",
    "cublasLt": "cublasLt64_12*.dll",
    "cudnn":    "cudnn64_*.dll",
}
missing = []
for name, pat in checks.items():
    found = try_load_any(pat)
    if found:
        print(f"[ok] {name}: {found}")
    else:
        print(f"[miss] {name}: pattern {pat} not found / cannot load")
        missing.append(name)

try:
    import ctranslate2
    print(f"[ct2] cuda_device_count={ctranslate2.get_cuda_device_count()}")
except Exception as e:
    print(f"[ct2] import/check failed: {e}")

try:
    import torch
    print(f"[torch] cuda.is_available()={torch.cuda.is_available()}")
except Exception as e:
    print(f"[torch] import/check failed: {e}")

if missing:
    sys.exit(2)
sys.exit(0)
PYEOF
  )
  exit_code=$?

  # 把 Python 输出按行回显到 precheck 日志（仅作信息提示，不阻断启动）
  if [ -n "$output" ]; then
    while IFS= read -r line; do
      [ -n "$line" ] && log_info "$line"
    done <<< "$output"
  fi

  if [ "$exit_code" -eq 0 ]; then
    return 0
  fi
  # 缺失 → log_warn 提示三种解决方向（不 log_err / 不 abort）
  log_warn "CUDA 运行时 DLL 检测未通过（cudart / cublas / cublasLt / cudnn 任一通配未加载成功）"
  log_info "解决方向 1: 后端 ASR 改用 int8 精度走 CPU，绕过 CUDA 运行时依赖"
  log_info "解决方向 2: pip install nvidia-cublas-cu12 nvidia-cudnn-cu12（仅装 PyPI 运行时轮子）"
  log_info "解决方向 3: 安装完整 CUDA Toolkit 12.x + 匹配 cuDNN（https://developer.nvidia.com/cuda-downloads）"
  return 1
}

install_cuda_toolkit() {
  log_dl "CUDA Toolkit 未安装 — 正在下载安装程序..."
  local cuda_url="https://developer.download.nvidia.com/compute/cuda/12.4.0/local_installers/cuda_12.4.0_windows.exe"
  local cuda_installer="$PROJECT_ROOT/tools/cuda_12.4.0_windows.exe"
  local cuda_dll_dir="$PROJECT_ROOT/tools/cuda/bin"

  mkdir -p "$PROJECT_ROOT/tools"

  if [ -f "$cuda_installer" ]; then
    log_info "CUDA 安装程序已存在: ${cuda_installer}"
  else
    log_info "下载 CUDA Toolkit 12.4.0 (~3GB)..."
    log_info "URL: ${cuda_url}"
    if command -v curl >/dev/null 2>&1; then
      curl -L --connect-timeout 60 --max-time 3600 -o "$cuda_installer" "$cuda_url" 2>&1 || {
        log_fail "curl 下载失败"
        return 1
      }
    elif command -v wget >/dev/null 2>&1; then
      wget -O "$cuda_installer" "$cuda_url" 2>&1 || {
        log_fail "wget 下载失败"
        return 1
      }
    else
      log_fail "无可用下载工具（curl/wget），请手动下载"
      log_info "下载后保存到: ${cuda_installer}"
      return 1
    fi
  fi

  if [ -s "$cuda_installer" ]; then
    local file_size
    file_size=$(powershell -Command "(Get-Item '${cuda_installer//\\/\\\\}').Length / 1MB" 2>/dev/null || echo "unknown")
    log_info "CUDA 安装程序大小: ${file_size} MB"
    log_dl "正在启动 CUDA Toolkit 安装程序..."
    log_info "=========================================="
    log_info "安装时请务必选择以下组件："
    log_info "  ✓ CUDA > Runtime Libraries > cuBLAS"
    log_info "  ✓ CUDA > Runtime Libraries > cuRAND"
    log_info "  ✓ CUDA > Runtime Libraries > cuDART"
    log_info "=========================================="
    log_info "安装完成后重启终端使 CUDA_PATH 生效"

    if [ "$OS" = "Windows_NT" ]; then
      local cuda_installer_win
      cuda_installer_win=$(echo "$cuda_installer" | sed 's|/|\\|g')
      cmd //c start "" "$cuda_installer_win" --silent --override
    else
      "$cuda_installer" --silent --override || {
        log_info "如需手动安装，请运行: $cuda_installer"
      }
    fi
    return 0
  else
    log_fail "CUDA 安装程序下载失败"
    rm -f "$cuda_installer"
    return 1
  fi
}

check_cuda_dll_functional() {
  if [ "$OS" != "Windows_NT" ]; then
    return 0
  fi
  log_info "测试 CUDA DLL 实际加载..."
  local test_script
  test_script="$PROJECT_ROOT/test_cuda_dll.py"
  local backend_path
  backend_path=$(echo "$PROJECT_ROOT/backend" | sed 's/\\/\\\\/g')
  echo "import sys; sys.path.insert(0, r'${backend_path}'); from app.services.asr_service import _check_cuda_dlls; exit(0 if _check_cuda_dlls() else 1)" > "$test_script"
  local test_result
  test_result=$(python "$test_script" 2>&1)
  local test_exit=$?
  rm -f "$test_script"
  if [ $test_exit -eq 0 ]; then
    log_ok "CUDA DLL 功能测试通过"
    return 0
  else
    log_warn "CUDA DLL 功能测试失败: ${test_result}"
    return 1
  fi
}

if check_cuda_toolkit; then
  check_cuda_compatibility
  check_cuda_dll_functional
  log_ok "CUDA Toolkit — 就绪"
elif check_cuda_dlls; then
  log_ok "CUDA 运行时库 — 就绪"
  export PATH="$PROJECT_ROOT/tools/cuda/bin:$PATH"
else
  # 不再自动下载/安装 CUDA Toolkit（会触发 ~3GB 下载、易因 URL 重定向产出
  # 0 字节占位文件，且与 start_all.sh 的非交互流程不匹配）。改为软警告，
  # 让后端走 CPU int8 兜底；如需 GPU 加速由用户手工安装。
  log_warn "CUDA Toolkit / 运行时库 — 未找到（已忽略，将走 CPU int8 兜底）"
  log_info "如需 GPU 加速，任选其一:"
  log_info "  1) 手动安装 CUDA Toolkit 12.x + 匹配 cuDNN（https://developer.nvidia.com/cuda-downloads）"
  log_info "  2) pip install nvidia-cublas-cu12 nvidia-cudnn-cu12 （仅 PyPI 运行时轮子）"
  log_info "  3) Settings → ASR 精度设为 int8（CPU 模式，默认兜底）"
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
  # 注意：qwen_tts 是可选依赖（TTS 功能），不阻塞安装流程；soundfile 是必备的音频处理库
  # `pip install -r requirements.txt`，避免 dev server / TTS 路由首次调用时 ImportError。
  for pkg in fastapi uvicorn faster-whisper opencc-python-reimplemented PyJWT bcrypt soundfile; do
    pip show "$pkg" >/dev/null 2>&1 || missing="$missing $pkg"
  done
  if [ -n "$missing" ]; then
    log_dl "Python 依赖缺失 (${missing# }) — 正在安装..."
    log_info "requirements.txt 路径: $PROJECT_ROOT/backend/requirements.txt"
    
    # 定义 pip 安装函数，支持重试和镜像源切换
    _pip_install_with_retry() {
      local timeout=120
      local attempt=1
      local pypi_url="https://pypi.org/simple"
      local tsinghua_url="https://pypi.tuna.tsinghua.edu.cn/simple"
      local aliyun_url="https://mirrors.aliyun.com/pypi/simple"
      
      # 尝试从默认源安装
      log_info "尝试第 ${attempt} 次安装（PyPI 默认源）..."
      log_info "命令: pip install -r backend/requirements.txt --timeout ${timeout} -q"
      log_info "镜像源: ${pypi_url}"
      if pip install -r "$PROJECT_ROOT/backend/requirements.txt" --timeout "$timeout" -q 2>&1; then
        return 0
      fi
      
      # 失败后尝试清华镜像
      attempt=$((attempt + 1))
      log_info "尝试第 ${attempt} 次安装（清华镜像）..."
      log_info "命令: pip install -r backend/requirements.txt --timeout ${timeout} -q -i ${tsinghua_url}"
      if pip install -r "$PROJECT_ROOT/backend/requirements.txt" --timeout "$timeout" -q \
        -i "${tsinghua_url}" 2>&1; then
        return 0
      fi
      
      # 尝试阿里云镜像
      attempt=$((attempt + 1))
      log_info "尝试第 ${attempt} 次安装（阿里云镜像）..."
      log_info "命令: pip install -r backend/requirements.txt --timeout ${timeout} -q -i ${aliyun_url}"
      if pip install -r "$PROJECT_ROOT/backend/requirements.txt" --timeout "$timeout" -q \
        -i "${aliyun_url}" 2>&1; then
        return 0
      fi
      
      return 1
    }
    
    if _pip_install_with_retry; then
      log_warn "Python 依赖 — 已安装"
    else
      log_fail "Python 依赖 — 安装失败"
      log_info "提示（中国大陆）：设置环境变量 export PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple 后重试"
      log_info "提示：或手动运行: pip install -r backend/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple"
    fi
  else
    log_ok "Python 依赖已安装"
  fi
else
  log_warn ".venv 无法激活，跳过依赖检查"
fi

# ── 5. FFmpeg / FFprobe ───────────────────────────────────────────────────────
# 缺失自动下载：固定使用 GyanD 的 ffmpeg-8.1-essentials_build（与 backend/.env 默认路径一致）
ensure_ffmpeg() {
  local target_dir="$PROJECT_ROOT/tools/ffmpeg/ffmpeg-8.1-essentials_build"
  local target_exe="$target_dir/bin/ffmpeg.exe"

  # 已就绪 → 不下
  if [ -f "$target_exe" ]; then
    return 0
  fi
  # 系统 PATH 上同时有 ffmpeg + ffprobe → 也不下（用户自备）
  if command -v ffmpeg >/dev/null 2>&1 && command -v ffprobe >/dev/null 2>&1; then
    return 0
  fi

  local url="https://github.com/GyanD/codexffmpeg/releases/download/8.1/ffmpeg-8.1-essentials_build.zip"
  local zip_path="$PROJECT_ROOT/tools/ffmpeg/ffmpeg-8.1-essentials_build.zip"
  mkdir -p "$PROJECT_ROOT/tools/ffmpeg"

  log_dl "FFmpeg 未找到 — 从 ${url} 下载（约 100 MB）..."
  if command -v curl >/dev/null 2>&1; then
    if ! curl -L --fail --progress-bar -o "$zip_path" "$url"; then
      log_fail "FFmpeg — 下载失败（curl）"
      rm -f "$zip_path"
      return 1
    fi
  elif command -v powershell >/dev/null 2>&1; then
    local zip_win
    zip_win=$(cygpath -w "$zip_path" 2>/dev/null || echo "$zip_path")
    if ! powershell -NonInteractive -Command "\$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri '${url}' -OutFile '${zip_win}'"; then
      log_fail "FFmpeg — 下载失败（powershell）"
      rm -f "$zip_path"
      return 1
    fi
  else
    log_fail "FFmpeg — 缺少 curl / powershell，无法自动下载"
    return 1
  fi

  log_dl "FFmpeg — 解压中..."
  if command -v unzip >/dev/null 2>&1; then
    if ! unzip -q -o "$zip_path" -d "$PROJECT_ROOT/tools/ffmpeg"; then
      log_fail "FFmpeg — 解压失败（unzip）"
      return 1
    fi
  elif command -v powershell >/dev/null 2>&1; then
    local zip_win dest_win
    zip_win=$(cygpath -w "$zip_path" 2>/dev/null || echo "$zip_path")
    dest_win=$(cygpath -w "$PROJECT_ROOT/tools/ffmpeg" 2>/dev/null || echo "$PROJECT_ROOT/tools/ffmpeg")
    if ! powershell -NonInteractive -Command "Expand-Archive -Path '${zip_win}' -DestinationPath '${dest_win}' -Force"; then
      log_fail "FFmpeg — 解压失败（powershell）"
      return 1
    fi
  else
    log_fail "FFmpeg — 缺少 unzip / powershell，无法自动解压"
    return 1
  fi

  rm -f "$zip_path"

  if [ -f "$target_exe" ]; then
    log_warn "FFmpeg — 已下载并解压到 tools/ffmpeg/ffmpeg-8.1-essentials_build/"
  else
    log_fail "FFmpeg — 解压后仍未找到 ${target_exe}"
    return 1
  fi
}

ensure_ffmpeg

# 把本地安装路径写回 backend/.env，让 backend 启动时能正确解析。
# 仅在当前 .env 值为空 / 裸 "ffmpeg"|"ffprobe"（PATH 查找）时覆盖，避免破坏用户自定义路径。
sync_ffmpeg_env() {
  local env_file="$PROJECT_ROOT/backend/.env"
  [ -f "$env_file" ] || return 0
  local local_ffmpeg="$PROJECT_ROOT/tools/ffmpeg/ffmpeg-8.1-essentials_build/bin/ffmpeg.exe"
  local local_ffprobe="$PROJECT_ROOT/tools/ffmpeg/ffmpeg-8.1-essentials_build/bin/ffprobe.exe"

  local target_ffmpeg="" target_ffprobe=""
  if [ -f "$local_ffmpeg" ] && [ -f "$local_ffprobe" ]; then
    target_ffmpeg="./tools/ffmpeg/ffmpeg-8.1-essentials_build/bin/ffmpeg.exe"
    target_ffprobe="./tools/ffmpeg/ffmpeg-8.1-essentials_build/bin/ffprobe.exe"
  else
    return 0  # 没有本地安装 — 不动 .env（用户可能依赖系统 PATH）
  fi

  local cur_ffmpeg cur_ffprobe
  cur_ffmpeg=$(grep -E '^[[:space:]]*FFMPEG_BIN=' "$env_file" 2>/dev/null \
    | head -1 | sed -E 's/^[[:space:]]*FFMPEG_BIN=//' || true)
  cur_ffprobe=$(grep -E '^[[:space:]]*FFPROBE_BIN=' "$env_file" 2>/dev/null \
    | head -1 | sed -E 's/^[[:space:]]*FFPROBE_BIN=//' || true)

  local changed=0
  case "$cur_ffmpeg" in
    ""|"ffmpeg"|"ffmpeg.exe")
      set_env_var "$env_file" "FFMPEG_BIN" "$target_ffmpeg" && changed=1 ;;
  esac
  case "$cur_ffprobe" in
    ""|"ffprobe"|"ffprobe.exe")
      set_env_var "$env_file" "FFPROBE_BIN" "$target_ffprobe" && changed=1 ;;
  esac

  if [ "$changed" -eq 1 ]; then
    log_warn "backend/.env — FFMPEG_BIN / FFPROBE_BIN 已指向 tools/ffmpeg 本地安装"
    export FFMPEG_BIN="$target_ffmpeg"
    export FFPROBE_BIN="$target_ffprobe"
  fi
}
sync_ffmpeg_env

check_ffbin "FFmpeg " "$FFMPEG_BIN"
check_ffbin "FFprobe" "$FFPROBE_BIN"

# ── 6. ASR 模型（列出全部已知模型，必备模型自动下载）──────────────────────
# 已知模型清单（与 backend/app/services/asr_service.py 的 ASR_MODEL_REPOS 对应）
ALL_KNOWN_MODELS=(small medium large-v3 large-v3-turbo)
# 必备模型：缺失时自动下载（其它模型仅展示状态，由用户在 UI 触发安装）
# medium 是 UI 默认推荐模型；其它（small / large-v3 / large-v3-turbo）按需在系统设置里安装。
ESSENTIAL_MODELS=(medium)

# 计算 model.bin 体积（MB），用于状态展示
_model_bin_size_mb() {
  local d="$1"
  local size_bytes
  size_bytes=$(wc -c < "${d}/model.bin" 2>/dev/null || echo 0)
  echo $((size_bytes / 1024 / 1024))
}

# 列出 data/asr_models/ 下所有目录（含未在 ALL_KNOWN_MODELS 里的）
_list_extra_cached_models() {
  local base="$PROJECT_ROOT/data/asr_models"
  [ -d "$base" ] || return 0
  for d in "$base"/faster-whisper-*/; do
    [ -d "$d" ] || continue
    local name="${d%/}"
    name="${name##*/faster-whisper-}"
    # 跳过已知模型（避免重复打印）
    local known=0
    for k in "${ALL_KNOWN_MODELS[@]}"; do
      [ "$k" = "$name" ] && known=1 && break
    done
    [ "$known" -eq 0 ] && echo "$name"
  done
}

if [ "$SKIP_ASR" -eq 1 ]; then
  log_info "ASR 模型检查已跳过（--skip-asr）"
else
  for model in "${ALL_KNOWN_MODELS[@]}"; do
    local_dir="$PROJECT_ROOT/data/asr_models/faster-whisper-${model}"
    if asr_model_cached "$model"; then
      size_mb=$(_model_bin_size_mb "$local_dir")
      log_ok "ASR 模型 ${model} — 就绪（${size_mb} MB）"
      continue
    fi

    # 判断是否必备
    is_essential=0
    for em in "${ESSENTIAL_MODELS[@]}"; do
      [ "$em" = "$model" ] && is_essential=1 && break
    done
    if [ "$is_essential" -eq 0 ]; then
      log_info "ASR 模型 ${model} — 未安装（可在系统设置中按需下载）"
      continue
    fi

    # 必备模型 → 自动下载
    log_dl "ASR 模型 ${model} — 未找到，开始下载（small≈500MB，medium≈1.5GB）..."
    log_info "Hugging Face 仓库: https://huggingface.co/Systran/faster-whisper-${model}"
      if activate_venv 2>/dev/null; then
        # PYTHONIOENCODING=utf-8: 避免 Windows 默认 cp1252 在 tqdm 中文/Unicode
        # 进度条字符上抛 UnicodeEncodeError
        PYTHONIOENCODING=utf-8 PYTHONUNBUFFERED=1 python - "$model" "$PROJECT_ROOT" <<'PYEOF'
import sys, os, shutil
from tqdm import tqdm

model = sys.argv[1]
project_root = sys.argv[2]
local_dir = os.path.join(project_root, 'data', 'asr_models', f'faster-whisper-{model}')
os.makedirs(local_dir, exist_ok=True)
ASR_MODEL_REPOS = {
    'small':          'Systran/faster-whisper-small',
    'medium':         'Systran/faster-whisper-medium',
    'large-v3':       'Systran/faster-whisper-large-v3',
    'large-v3-turbo': 'deepdml/faster-whisper-large-v3-turbo-ct2',
}
repo_id = ASR_MODEL_REPOS.get(model, f'Systran/faster-whisper-{model}')

class TqdmProgressCallback(tqdm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, unit='B', unit_scale=True, bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]')
        self._lock = __import__('threading').Lock()

    def _should_update(self, current, total):
        return True

def _do_download(repo_id, local_dir):
    from huggingface_hub import snapshot_download
    from huggingface_hub.utils._progress import QuadraticSpeedupDelayFilter

    progress = TqdmProgressCallback(desc=f'下载 {repo_id}', initial=0, dynamic_ncols=True)

    def _progress_callback(chunk_size, file_size, download_speed, **_):
        if file_size and file_size > 0:
            progress.total = file_size
            progress.update(chunk_size)

    try:
        snapshot_download(
            repo_id=repo_id,
            local_dir=local_dir,
            local_dir_use_symlinks=False,
            progress_callback=_progress_callback,
        )
    except TypeError:
        # huggingface_hub >= 0.24 移除 progress_callback 参数
        snapshot_download(repo_id=repo_id, local_dir=local_dir, local_dir_use_symlinks=False)
    finally:
        progress.close()

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
    # 优先尝试 CUDA；不可用则退回 CPU（仅用于校验模型完整性，不缓存模型实例）
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            WhisperModel(local_dir, device='cuda', compute_type='float16')
        else:
            WhisperModel(local_dir, device='cpu', compute_type='int8')
    except Exception:
        WhisperModel(local_dir, device='cpu', compute_type='int8')
except Exception as e:
    print(f'[precheck]      验证失败: {e}', file=sys.stderr, flush=True)
    sys.exit(1)
PYEOF
        py_exit=$?
        if [ $py_exit -eq 0 ]; then
          log_warn "ASR 模型 ${model} — 已下载并就绪"
        else
          # 降级为 warn：模型下载失败不应阻断 start_all（用户可在 Settings UI
          # 中按需触发下载，或用 HF mirror / 离线复制）。
          log_warn "ASR 模型 ${model} — 下载失败（不阻断启动，可在 Settings 中重试）"
          log_info "提示（中国大陆）：export HF_ENDPOINT=https://hf-mirror.com 后重试"
          log_info "提示（离线）：从工作机复制 ~/.cache/huggingface/hub/models--Systran--faster-whisper-${model}/"
        fi
      else
        log_warn "ASR 模型 ${model} — 无法下载（.venv 未就绪，可在 Settings 中重试）"
      fi
  done

  # 列出额外（已知清单之外）的缓存模型，方便发现"非标准目录名"的旧下载
  while IFS= read -r extra; do
    [ -z "$extra" ] && continue
    extra_dir="$PROJECT_ROOT/data/asr_models/faster-whisper-${extra}"
    if _verify_asr_model_dir "$extra_dir"; then
      size_mb=$(_model_bin_size_mb "$extra_dir")
      log_info "ASR 模型 ${extra} — 已缓存但不在已知清单中（${size_mb} MB）"
    fi
  done < <(_list_extra_cached_models)
fi

# ── 7. 数据库锁 ───────────────────────────────────────────────────────────────
check_db_lock

# ── 8. 端口 8000 + 5173 ───────────────────────────────────────────────────────
# 先尝试常规释放
free_port 8000
free_port 5173

# 二次验证：如果还有真活进程占用，调用 stop_all.sh 做更彻底的清理
_port_active_pids() {
  local port="$1"
  local pids alive=""
  pids=$(netstat -ano 2>/dev/null \
    | awk -v p=":${port}" '$1~/TCP|UDP/ && ($2~p" " || $2~p"$") {print $NF}' \
    | sort -u | grep -E '^[0-9]+$' || true)
  for pid in $pids; do
    # PID 0 = System Idle Process（内核占位），不是真活进程
    [ "$pid" = "0" ] && continue
    if tasklist //FI "PID eq ${pid}" 2>/dev/null | grep -q "[[:space:]]${pid}[[:space:]]"; then
      # 还要排除 tasklist 把 PID 0 渲染为 "System Idle Process" 的情形（防御性）
      local proc_name
      proc_name=$(tasklist //FI "PID eq ${pid}" //FO CSV //NH 2>/dev/null | head -1 | awk -F'","' '{print $1}' | tr -d '"' || true)
      if [ "$proc_name" = "System Idle Process" ] || [ "$proc_name" = "System" ]; then
        continue
      fi
      alive="${alive} ${pid}"
    fi
  done
  echo "${alive# }"
}

still_8000="$(_port_active_pids 8000)"
still_5173="$(_port_active_pids 5173)"
if [ -n "$still_8000" ] || [ -n "$still_5173" ]; then
  log_warn "端口仍被活进程占用（8000=${still_8000:-空} / 5173=${still_5173:-空}），调用 stop_all.sh 彻底清理..."
  if [ -x "$PROJECT_ROOT/scripts/stop_all.sh" ]; then
    bash "$PROJECT_ROOT/scripts/stop_all.sh" || true
  else
    bash "$PROJECT_ROOT/scripts/stop_all.sh" || true
  fi
  sleep 1
  # 复检
  still_8000="$(_port_active_pids 8000)"
  still_5173="$(_port_active_pids 5173)"
  if [ -z "$still_8000" ] && [ -z "$still_5173" ]; then
    log_ok "stop_all.sh 已彻底释放端口"
  else
    log_fail "stop_all.sh 后仍残留：8000=${still_8000:-空} / 5173=${still_5173:-空}"
  fi
fi

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
