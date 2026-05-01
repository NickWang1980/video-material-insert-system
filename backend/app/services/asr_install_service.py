"""Async download manager for ASR (faster-whisper) models.

Downloads to `data/asr_models/faster-whisper-{model}/` via a child Python
process running `huggingface_hub.snapshot_download`. The subprocess design
is what makes mid-download cancellation possible — we kill the child to
abort, then `shutil.rmtree` the partial files.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from ..utils.logger import get_logger
from .asr_service import (
    ASR_MODEL_REPOS,
    ASR_MODEL_SIZES_MB,
    _normalize_asr_model,
    check_model_integrity,
)

logger = get_logger()

_install_jobs: dict[str, dict] = {}
_install_lock = threading.Lock()
_install_active_models: set[str] = set()


def is_model_installed(model_name: str, data_dir: Path) -> bool:
    ok, _ = check_model_integrity(model_name, data_dir)
    return ok


def diagnose_model(model_name: str, data_dir: Path) -> tuple[bool, str | None]:
    return check_model_integrity(model_name, data_dir)


def get_model_size_mb(model_name: str) -> int:
    return ASR_MODEL_SIZES_MB.get(_normalize_asr_model(model_name), 0)


def get_progress(task_id: str) -> dict | None:
    with _install_lock:
        info = _install_jobs.get(task_id)
        if not info:
            return None
        # 过滤内部对象（subprocess.Popen 不可 JSON 序列化）
        return {k: v for k, v in info.items() if not k.startswith("_")}


def start_install(model_name: str, data_dir: Path) -> str:
    model = _normalize_asr_model(model_name)
    task_id = uuid.uuid4().hex
    with _install_lock:
        if model in _install_active_models:
            for tid, info in _install_jobs.items():
                if info.get("model") == model and info.get("status") in ("queued", "downloading"):
                    return tid
        _install_active_models.add(model)
        _install_jobs[task_id] = {
            "model": model,
            "status": "queued",
            "progress": 0,
            "message": "排队中",
            "total_mb": ASR_MODEL_SIZES_MB.get(model, 0),
            "cancel_requested": False,
            "_proc": None,
        }
    threading.Thread(
        target=_run_install, args=(task_id, model, data_dir), daemon=True
    ).start()
    return task_id


def cancel_install(task_id: str) -> tuple[bool, str]:
    """请求取消下载。立即 kill 子进程并清理本地目录。"""
    with _install_lock:
        info = _install_jobs.get(task_id)
        if not info:
            return False, "任务不存在"
        if info.get("status") not in ("queued", "downloading"):
            return False, f"任务已经处于 {info.get('status')} 状态"
        info["cancel_requested"] = True
        proc = info.get("_proc")
    if proc is not None:
        try:
            proc.kill()
        except Exception:
            pass
    return True, "已请求取消"


def list_installed_models(data_dir: Path) -> list[dict]:
    """列出全部已知模型在项目本地 + HF 缓存的安装状态、路径、大小。"""
    base = data_dir / "asr_models"
    hf_cache = _hf_cache_dir()
    results: list[dict] = []
    for model_name, repo_id in ASR_MODEL_REPOS.items():
        local_dir = base / f"faster-whisper-{model_name}"
        local_size = _dir_size_bytes(local_dir)
        ok, reason = check_model_integrity(model_name, data_dir)

        # HF 缓存目录格式：~/.cache/huggingface/hub/models--<org>--<repo>/
        hf_safe = repo_id.replace("/", "--")
        hf_dir = hf_cache / f"models--{hf_safe}" if hf_cache else None
        hf_size = _dir_size_bytes(hf_dir) if hf_dir and hf_dir.exists() else 0

        results.append({
            "model": model_name,
            "repo": repo_id,
            "installed": ok,
            "reason": None if ok else reason,
            "size_hint_mb": ASR_MODEL_SIZES_MB.get(model_name, 0),
            "local_path": str(local_dir),
            "local_exists": local_dir.exists(),
            "local_size_bytes": local_size,
            "hf_cache_path": str(hf_dir) if hf_dir else None,
            "hf_cache_exists": bool(hf_dir and hf_dir.exists()),
            "hf_cache_size_bytes": hf_size,
        })
    return results


def delete_model(model_name: str, data_dir: Path, *, include_hf_cache: bool = False) -> dict:
    """删除模型本地目录（默认不动 HF 缓存）。返回各路径删除结果。"""
    model = _normalize_asr_model(model_name)
    repo_id = ASR_MODEL_REPOS.get(model)
    base = data_dir / "asr_models"
    local_dir = base / f"faster-whisper-{model}"

    result = {
        "model": model,
        "local_deleted": False,
        "local_path": str(local_dir),
        "hf_cache_deleted": False,
        "hf_cache_path": None,
    }

    if local_dir.exists():
        try:
            shutil.rmtree(local_dir, ignore_errors=False)
            result["local_deleted"] = True
        except Exception as e:
            logger.exception(f"Delete local model dir failed: {local_dir}")
            shutil.rmtree(local_dir, ignore_errors=True)
            result["local_deleted"] = not local_dir.exists()
            result["local_error"] = str(e)[:200]

    if include_hf_cache and repo_id:
        hf_cache = _hf_cache_dir()
        if hf_cache:
            hf_safe = repo_id.replace("/", "--")
            hf_dir = hf_cache / f"models--{hf_safe}"
            result["hf_cache_path"] = str(hf_dir)
            if hf_dir.exists():
                try:
                    shutil.rmtree(hf_dir, ignore_errors=False)
                    result["hf_cache_deleted"] = True
                except Exception as e:
                    shutil.rmtree(hf_dir, ignore_errors=True)
                    result["hf_cache_deleted"] = not hf_dir.exists()
                    result["hf_cache_error"] = str(e)[:200]

    return result


def _set(task_id: str, **kw) -> None:
    with _install_lock:
        if task_id in _install_jobs:
            _install_jobs[task_id].update(kw)


def _hf_cache_dir() -> Path | None:
    env = os.environ.get("HF_HUB_CACHE")
    if env:
        return Path(env)
    home_cache = os.environ.get("XDG_CACHE_HOME")
    if home_cache:
        return Path(home_cache) / "huggingface" / "hub"
    home = Path.home() if Path.home() else None
    if home:
        return home / ".cache" / "huggingface" / "hub"
    return None


def _dir_size_bytes(path: Path | None) -> int:
    if not path or not path.exists():
        return 0
    total = 0
    try:
        for f in path.rglob("*"):
            try:
                if f.is_file():
                    total += f.stat().st_size
            except OSError:
                continue
    except Exception:
        pass
    return total


_DOWNLOAD_SCRIPT = """\
import os, sys
repo_id = sys.argv[1]
local_dir = sys.argv[2]
from huggingface_hub import snapshot_download
try:
    snapshot_download(repo_id=repo_id, local_dir=local_dir, local_dir_use_symlinks=False)
except TypeError:
    snapshot_download(repo_id=repo_id, local_dir=local_dir)
"""


def _run_install(task_id: str, model_name: str, data_dir: Path) -> None:
    repo_id = ASR_MODEL_REPOS.get(model_name)
    if not repo_id:
        _set(task_id, status="failed", message=f"未知模型: {model_name}")
        with _install_lock:
            _install_active_models.discard(model_name)
        return

    local_dir = data_dir / "asr_models" / f"faster-whisper-{model_name}"
    local_dir.mkdir(parents=True, exist_ok=True)
    total_bytes = max(1, ASR_MODEL_SIZES_MB.get(model_name, 1) * 1024 * 1024)

    _set(task_id, status="downloading", message=f"从 {repo_id} 启动下载...")

    try:
        proc = subprocess.Popen(
            [sys.executable, "-c", _DOWNLOAD_SCRIPT, repo_id, str(local_dir)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=os.environ.copy(),
        )
    except Exception as e:
        _set(task_id, status="failed", message=f"无法启动下载子进程: {e}")
        with _install_lock:
            _install_active_models.discard(model_name)
        return

    with _install_lock:
        if task_id in _install_jobs:
            _install_jobs[task_id]["_proc"] = proc

    # 轮询进度 + 检查取消
    cancelled = False
    while proc.poll() is None:
        with _install_lock:
            cancelled = _install_jobs.get(task_id, {}).get("cancel_requested", False)
        if cancelled:
            try:
                proc.kill()
                proc.wait(timeout=5)
            except Exception:
                pass
            break
        try:
            size = _dir_size_bytes(local_dir)
            pct = min(99, int(size / total_bytes * 100))
            _set(
                task_id,
                progress=pct,
                message=f"已下载 {size // (1024 * 1024)} MB / {total_bytes // (1024 * 1024)} MB",
            )
        except Exception:
            pass
        time.sleep(1.0)

    if cancelled:
        # 清理已下载的部分文件
        shutil.rmtree(local_dir, ignore_errors=True)
        _set(task_id, status="cancelled", progress=0, message="已取消，已清理部分下载的文件")
        logger.info(f"ASR install cancelled: {model_name}")
        with _install_lock:
            _install_active_models.discard(model_name)
        return

    # 子进程已自然退出，检查结果
    if proc.returncode == 0:
        # 校验完整性（防止子进程异常但 returncode=0 的边缘情况）
        ok, reason = check_model_integrity(model_name, data_dir)
        if ok:
            _set(task_id, status="completed", progress=100, message="安装完成")
            logger.info(f"ASR model installed: {model_name} -> {local_dir}")
        else:
            shutil.rmtree(local_dir, ignore_errors=True)
            _set(task_id, status="failed", message=f"下载完成但完整性校验失败: {reason}")
    else:
        stderr_text = ""
        try:
            if proc.stderr:
                stderr_text = proc.stderr.read().decode("utf-8", errors="ignore").strip()
        except Exception:
            pass
        if "WinError 1314" in stderr_text:
            shutil.rmtree(local_dir, ignore_errors=True)
            _set(
                task_id,
                status="failed",
                message="WinError 1314 — 请开启 Windows 开发人员模式后重试",
            )
        else:
            _set(
                task_id,
                status="failed",
                message=(stderr_text or f"下载失败（退出码 {proc.returncode}）")[:400],
            )
        logger.warning(f"ASR install failed: model={model_name} stderr={stderr_text[:300]}")

    with _install_lock:
        _install_active_models.discard(model_name)
