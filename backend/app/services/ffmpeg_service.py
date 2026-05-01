"""FFmpeg / FFprobe 工具链检视：路径、版本、编译特性、硬件编码器、文件大小。

只读接口，配合系统设置页的"FFmpeg 工具管理"面板。路径来源仍是 backend/.env
（FFMPEG_BIN / FFPROBE_BIN），本服务不修改配置，只汇报现状。
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from ..utils.encoder_utils import list_available_hw_encoders

_VERSION_RE = re.compile(r"^(?:ffmpeg|ffprobe)\s+version\s+(\S+)", re.IGNORECASE)


def _which(bin_path: str) -> Path | None:
    """把 bin_path（可能是相对路径、可能是命令名）解析成实际可执行文件的绝对路径。"""
    p = Path(bin_path)
    if p.is_absolute() and p.exists():
        return p.resolve()
    if p.is_file() or p.exists():
        return p.resolve()
    found = shutil.which(bin_path)
    return Path(found).resolve() if found else None


def _file_size(path: Path | None) -> int:
    if not path or not path.exists():
        return 0
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _run_version(bin_path: str) -> tuple[bool, str, str, str]:
    """返回 (ok, version, configuration_line, raw_first_line)。"""
    try:
        proc = subprocess.run(
            [bin_path, "-hide_banner", "-version"],
            capture_output=True, text=True, timeout=8,
        )
    except FileNotFoundError:
        return False, "", "", "可执行文件未找到"
    except subprocess.TimeoutExpired:
        return False, "", "", "执行超时"
    except Exception as e:
        return False, "", "", f"无法运行：{e}"
    if proc.returncode != 0:
        return False, "", "", proc.stderr.strip()[:200] or proc.stdout.strip()[:200]

    out = proc.stdout or ""
    first_line = out.splitlines()[0] if out else ""
    m = _VERSION_RE.match(first_line)
    version = m.group(1) if m else ""
    config_line = ""
    for line in out.splitlines():
        if line.startswith("configuration:"):
            config_line = line[len("configuration:"):].strip()
            break
    return True, version, config_line, first_line


def get_ffmpeg_info(ffmpeg_bin: str) -> dict:
    resolved = _which(ffmpeg_bin)
    info: dict = {
        "configured_path": ffmpeg_bin,
        "resolved_path": str(resolved) if resolved else None,
        "exists": resolved is not None,
        "size_bytes": _file_size(resolved),
        "version": "",
        "first_line": "",
        "configuration": "",
        "hw_encoders": [],
        "ok": False,
        "error": None,
    }
    if not resolved:
        info["error"] = "可执行文件未找到（检查 backend/.env 的 FFMPEG_BIN）"
        return info

    ok, version, config, first_line = _run_version(str(resolved))
    info["ok"] = ok
    info["version"] = version
    info["first_line"] = first_line
    info["configuration"] = config
    if ok:
        # 硬件编码器探测（已带缓存）
        try:
            avail = list_available_hw_encoders(str(resolved))
            info["hw_encoders"] = sorted(avail)
        except Exception:
            info["hw_encoders"] = []
    else:
        info["error"] = first_line  # 这里 first_line 在失败路径里被复用为错误描述
    return info


def get_ffprobe_info(ffprobe_bin: str) -> dict:
    resolved = _which(ffprobe_bin)
    info: dict = {
        "configured_path": ffprobe_bin,
        "resolved_path": str(resolved) if resolved else None,
        "exists": resolved is not None,
        "size_bytes": _file_size(resolved),
        "version": "",
        "first_line": "",
        "ok": False,
        "error": None,
    }
    if not resolved:
        info["error"] = "可执行文件未找到（检查 backend/.env 的 FFPROBE_BIN）"
        return info
    ok, version, _config, first_line = _run_version(str(resolved))
    info["ok"] = ok
    info["version"] = version
    info["first_line"] = first_line
    if not ok:
        info["error"] = first_line
    return info
