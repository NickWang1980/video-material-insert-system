"""Video Gen — master-side HTTP client for the heygem digital-human sidecar.

Responsibilities
----------------
* Resolve the 3 audio sources (upload | tts | material) and 3 reference-video
  sources (upload | source | material) into concrete filesystem paths.
* POST multipart to heygem `/api/heygem/synthesize`, persist `heygem_work_id`.
* Spawn a background daemon thread per task that polls heygem `/status`,
  streams `/result` to `data/video_gen/{task_id}.mp4` on success, and
  updates the `video_gen_tasks` row's status/phase/progress.
* Provide `resume_running_tasks(settings)` for the startup hook — Phase-1
  marks all in-flight tasks as `interrupted` (re-attach is Phase-2).

Logging: uses stdlib `logging.getLogger("video_gen_service")` so the
loguru bridge in `app/utils/logger.py` routes everything into
`video_gen_<ts>.log` alongside the FFmpeg video_service logs.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

from ..config import Settings
from ..models.database import SessionLocal
from ..models.material import Material
from ..models.source_video_entry import SourceVideoEntry
from ..models.video_gen import VideoGenTask


logger = logging.getLogger("video_gen_service")


# ---- httpx client singleton -----------------------------------------------
_client: Optional[httpx.Client] = None
_client_lock = threading.Lock()


def _get_client(settings: Settings) -> httpx.Client:
    global _client
    if _client is not None:
        return _client
    with _client_lock:
        if _client is None:
            _client = httpx.Client(
                base_url=settings.heygem_base_url.rstrip("/"),
                timeout=httpx.Timeout(
                    connect=10.0,
                    read=float(settings.heygem_request_timeout),
                    write=float(settings.heygem_request_timeout),
                    pool=10.0,
                ),
            )
        return _client


# ---- Health ---------------------------------------------------------------
def get_health(settings: Settings) -> dict:
    """Returns a flat dict the API layer maps to VideoGenHealthResponse."""
    if not settings.heygem_enabled:
        return {
            "enabled": False,
            "reachable": False,
            "base_url": settings.heygem_base_url,
            "detail": "heygem disabled via settings (HEYGEM_ENABLED=0)",
        }
    try:
        r = _get_client(settings).get("/api/heygem/health", timeout=5.0)
        r.raise_for_status()
        data = r.json()
        return {
            "enabled": True,
            "reachable": True,
            "base_url": settings.heygem_base_url,
            "heygem_ready": bool(data.get("ready")),
            "heygem_gpu": data.get("gpu") or None,
            "heygem_version": data.get("version") or None,
            "detail": data.get("init_error"),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("[video_gen] heygem health probe failed: %s", exc)
        return {
            "enabled": True,
            "reachable": False,
            "base_url": settings.heygem_base_url,
            "detail": f"{type(exc).__name__}: {exc}",
        }


# ---- Sidecar process launcher --------------------------------------------
def start_heygem_sidecar(settings: Settings) -> dict:
    """Launch `vendor/heygem/start_api.bat` in a new detached console window.

    Idempotent: probes /health first; if already reachable, returns
    `already_running=True` without spawning anything. Windows-only (other
    platforms get a friendly error).

    Returns a flat dict:
        {started: bool, already_running: bool, pid: int|None,
         bat_path: str, detail: str}
    """
    h = get_health(settings)
    if h.get("reachable"):
        return {
            "started": False,
            "already_running": True,
            "pid": None,
            "bat_path": "",
            "detail": "heygem 已经在跑（/health 可达），无需重启",
        }

    if sys.platform != "win32":
        return {
            "started": False,
            "already_running": False,
            "pid": None,
            "bat_path": "",
            "detail": f"auto-start 仅支持 Windows，当前平台：{sys.platform}",
        }

    # backend/app/services/video_gen_service.py → project root → vendor/heygem
    repo_root = Path(__file__).resolve().parents[3]
    bat = repo_root / "vendor" / "heygem" / "start_api.bat"
    if not bat.exists():
        return {
            "started": False,
            "already_running": False,
            "pid": None,
            "bat_path": str(bat),
            "detail": (
                f"start_api.bat 不存在：{bat}。"
                "请先 `git submodule update --init`，或在 Settings 把"
                "HEYGEM_BASE_URL 指向你已部署的 heygem 实例。"
            ),
        }

    try:
        # CREATE_NEW_CONSOLE = 0x00000010 — 让 cmd 在新可见窗口运行（用户能看见日志）
        # 这跟 scripts/start_all.bat --with-heygem 走的是同一条路径
        proc = subprocess.Popen(
            ["cmd.exe", "/k", str(bat)],
            cwd=str(bat.parent),
            creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0x00000010),
            close_fds=True,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("[video_gen] heygem auto-start failed: %s", exc)
        return {
            "started": False,
            "already_running": False,
            "pid": None,
            "bat_path": str(bat),
            "detail": f"{type(exc).__name__}: {exc}",
        }

    logger.info(
        "[video_gen] spawned heygem sidecar (pid=%s) — cmd window will show logs; "
        "frontend should poll /health to detect ready",
        proc.pid,
    )
    return {
        "started": True,
        "already_running": False,
        "pid": proc.pid,
        "bat_path": str(bat),
        "detail": (
            "已在独立 cmd 窗口启动 heygem。首次约 30-90s（pip install + wenet 模型加载）。"
            "前端会自动轮询 /health，就绪后状态条变绿。"
        ),
    }


# ---- Source resolution ----------------------------------------------------
class SourceResolutionError(Exception):
    pass


def resolve_audio_source(
    settings: Settings,
    *,
    source_type: str,
    source_ref: Optional[str],
    uploaded_path: Optional[Path],
) -> Path:
    """Return an absolute path to the audio file (wav/mp3) to send to heygem."""
    if source_type == "upload":
        if uploaded_path is None or not uploaded_path.exists():
            raise SourceResolutionError("upload audio missing on disk")
        return uploaded_path
    if source_type == "tts":
        # source_ref is the filename under data/outputs/tts/ (or full URL ending
        # /api/tts/audio/<name>) — both TTS history forms are accepted.
        if not source_ref:
            raise SourceResolutionError("tts source_ref required")
        name = source_ref.rsplit("/", 1)[-1]
        p = settings.data_dir / "outputs" / "tts" / name
        if not p.exists():
            raise SourceResolutionError(f"tts history audio not found on disk: {name}")
        return p
    if source_type == "material":
        if not source_ref:
            raise SourceResolutionError("material source_ref required (material id)")
        try:
            mat_id = int(source_ref)
        except ValueError:
            raise SourceResolutionError(f"invalid material id: {source_ref!r}")
        with SessionLocal() as db:
            mat = db.get(Material, mat_id)
        if mat is None or mat.file_type != "audio":
            raise SourceResolutionError(f"material {mat_id} not found or not audio")
        p = Path(mat.file_path)
        if not p.is_absolute():
            p = (settings.data_dir.parent / p).resolve()
        if not p.exists():
            raise SourceResolutionError(f"material audio file missing: {p}")
        return p
    raise SourceResolutionError(f"unknown audio_source_type: {source_type}")


def resolve_video_source(
    settings: Settings,
    *,
    source_type: str,
    source_ref: Optional[str],
    uploaded_path: Optional[Path],
) -> Path:
    if source_type == "upload":
        if uploaded_path is None or not uploaded_path.exists():
            raise SourceResolutionError("upload video missing on disk")
        return uploaded_path
    if source_type == "source":
        if not source_ref:
            raise SourceResolutionError("source video id required")
        try:
            sv_id = int(source_ref)
        except ValueError:
            raise SourceResolutionError(f"invalid source video id: {source_ref!r}")
        with SessionLocal() as db:
            sv = db.get(SourceVideoEntry, sv_id)
        if sv is None:
            raise SourceResolutionError(f"source video entry {sv_id} not found")
        p = Path(sv.video_path)
        if not p.is_absolute():
            p = (settings.data_dir.parent / p).resolve()
        if not p.exists():
            raise SourceResolutionError(f"source video file missing: {p}")
        return p
    if source_type == "material":
        if not source_ref:
            raise SourceResolutionError("material id required")
        try:
            mat_id = int(source_ref)
        except ValueError:
            raise SourceResolutionError(f"invalid material id: {source_ref!r}")
        with SessionLocal() as db:
            mat = db.get(Material, mat_id)
        if mat is None or mat.file_type != "video":
            raise SourceResolutionError(f"material {mat_id} not found or not video")
        p = Path(mat.file_path)
        if not p.is_absolute():
            p = (settings.data_dir.parent / p).resolve()
        if not p.exists():
            raise SourceResolutionError(f"material video file missing: {p}")
        return p
    raise SourceResolutionError(f"unknown video_source_type: {source_type}")


# ---- Task creation --------------------------------------------------------
def create_task(
    settings: Settings,
    *,
    task_name: Optional[str],
    audio_source_type: str,
    audio_source_ref: Optional[str],
    audio_uploaded: Optional[Path],
    video_source_type: str,
    video_source_ref: Optional[str],
    video_uploaded: Optional[Path],
) -> VideoGenTask:
    if not settings.heygem_enabled:
        raise RuntimeError("heygem is disabled via settings")
    audio_path = resolve_audio_source(
        settings,
        source_type=audio_source_type,
        source_ref=audio_source_ref,
        uploaded_path=audio_uploaded,
    )
    video_path = resolve_video_source(
        settings,
        source_type=video_source_type,
        source_ref=video_source_ref,
        uploaded_path=video_uploaded,
    )
    logger.info(
        "[video_gen] create_task audio_src=%s video_src=%s audio=%s video=%s",
        audio_source_type, video_source_type, audio_path.name, video_path.name,
    )

    with SessionLocal() as db:
        task = VideoGenTask(
            task_name=task_name,
            audio_source_type=audio_source_type,
            audio_source_ref=audio_source_ref,
            audio_path=str(audio_path),
            video_source_type=video_source_type,
            video_source_ref=video_source_ref,
            video_path=str(video_path),
            status="pending",
            phase="staging",
            progress=0,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        task_id = task.id

    # Hand off to heygem (multipart POST) and kick polling thread.
    threading.Thread(
        target=_submit_and_poll,
        args=(task_id, settings, audio_path, video_path),
        daemon=True,
        name=f"video-gen-job-{task_id}",
    ).start()

    with SessionLocal() as db:
        return db.get(VideoGenTask, task_id)


def _submit_and_poll(
    task_id: int,
    settings: Settings,
    audio_path: Path,
    video_path: Path,
) -> None:
    client = _get_client(settings)
    # 1) POST to heygem
    try:
        with audio_path.open("rb") as af, video_path.open("rb") as vf:
            files = {
                "audio_file": (audio_path.name, af, "application/octet-stream"),
                "video_file": (video_path.name, vf, "application/octet-stream"),
            }
            r = client.post("/api/heygem/synthesize", files=files)
        r.raise_for_status()
        work_id = r.json()["work_id"]
        logger.info("[video_gen] task=%s heygem accepted work_id=%s", task_id, work_id)
        _update_task(task_id, heygem_work_id=work_id, status="running", phase="submitted", progress=1)
    except Exception as exc:  # noqa: BLE001
        logger.exception("[video_gen] task=%s heygem submit failed: %s", task_id, exc)
        _update_task(task_id, status="failed", error_message=f"submit: {exc}", completed_at=datetime.utcnow())
        return

    # 2) Poll
    while True:
        time.sleep(3.0)
        try:
            r = client.get(f"/api/heygem/status/{work_id}")
            r.raise_for_status()
            s = r.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[video_gen] task=%s poll error: %s (retrying)", task_id, exc)
            continue
        _update_task(
            task_id,
            phase=str(s.get("phase") or ""),
            progress=int(s.get("percent") or 0),
        )
        if s.get("completed"):
            if s.get("success"):
                _download_result(task_id, work_id, settings)
            else:
                err = str(s.get("error") or s.get("message") or "unknown")
                logger.error("[video_gen] task=%s heygem reported failure: %s", task_id, err)
                _update_task(
                    task_id,
                    status="failed",
                    error_message=err,
                    completed_at=datetime.utcnow(),
                )
            return


def _download_result(task_id: int, work_id: str, settings: Settings) -> None:
    out_dir = settings.data_dir / "video_gen"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{task_id}.mp4"
    client = _get_client(settings)
    try:
        with client.stream("GET", f"/api/heygem/result/{work_id}") as r:
            r.raise_for_status()
            with out_path.open("wb") as f:
                for chunk in r.iter_bytes(1 << 20):
                    f.write(chunk)
    except Exception as exc:  # noqa: BLE001
        logger.exception("[video_gen] task=%s download failed: %s", task_id, exc)
        _update_task(
            task_id,
            status="failed",
            error_message=f"download: {exc}",
            completed_at=datetime.utcnow(),
        )
        return
    logger.info("[video_gen] task=%s result saved → %s (%s bytes)", task_id, out_path, out_path.stat().st_size)
    _update_task(
        task_id,
        status="succeeded",
        phase="done",
        progress=100,
        result_path=str(out_path),
        completed_at=datetime.utcnow(),
    )


def _update_task(task_id: int, **fields) -> None:
    with SessionLocal() as db:
        task = db.get(VideoGenTask, task_id)
        if task is None:
            return
        for k, v in fields.items():
            setattr(task, k, v)
        task.updated_at = datetime.utcnow()
        db.commit()


# ---- Cancellation ---------------------------------------------------------
def cancel_task(task_id: int) -> bool:
    """Mark task as cancelled (heygem has no cancel API; in-flight job keeps
    running on the sidecar but its result will be discarded)."""
    with SessionLocal() as db:
        task = db.get(VideoGenTask, task_id)
        if task is None:
            return False
        if task.status in ("succeeded", "failed", "cancelled"):
            return False
        task.status = "cancelled"
        task.completed_at = datetime.utcnow()
        task.updated_at = datetime.utcnow()
        db.commit()
    logger.info("[video_gen] task=%s cancelled", task_id)
    return True


# ---- Startup recovery -----------------------------------------------------
def resume_running_tasks(settings: Settings) -> None:
    """Phase-1: mark in-flight tasks as `interrupted`. Phase-2 re-attaches."""
    with SessionLocal() as db:
        tasks = db.query(VideoGenTask).filter(VideoGenTask.status.in_(["pending", "running"])).all()
        n = 0
        for t in tasks:
            t.status = "interrupted"
            t.error_message = (t.error_message or "") + " | backend restarted while task was in-flight"
            t.completed_at = datetime.utcnow()
            t.updated_at = datetime.utcnow()
            n += 1
        if n:
            db.commit()
            logger.warning("[video_gen] startup: marked %d in-flight task(s) as interrupted", n)


# ---- Save-to-material handoff --------------------------------------------
def save_to_material_library(
    task_id: int,
    settings: Settings,
    *,
    library_kind: str = "unfiled",
    product_id: Optional[int] = None,
    script_folder_id: Optional[int] = None,
    display_name: Optional[str] = None,
) -> int:
    """Copy data/video_gen/{id}.mp4 into the materials library and create a row."""
    with SessionLocal() as db:
        task = db.get(VideoGenTask, task_id)
        if task is None:
            raise ValueError(f"task {task_id} not found")
        if task.status != "succeeded" or not task.result_path:
            raise ValueError(f"task {task_id} has no successful result")
        src = Path(task.result_path)
        if not src.exists():
            raise ValueError(f"result file missing on disk: {src}")
        # Drop into the standard materials layout
        kind_dir = {"general": "general", "product": "products", "unfiled": "unfiled"}[library_kind]
        dst_dir = settings.data_dir / "uploads" / "materials" / kind_dir / "videos"
        dst_dir.mkdir(parents=True, exist_ok=True)
        base = display_name or f"video_gen_{task_id}.mp4"
        if not base.lower().endswith(".mp4"):
            base = base + ".mp4"
        dst = dst_dir / base
        i = 1
        while dst.exists():
            dst = dst_dir / f"{Path(base).stem}_{i}.mp4"
            i += 1
        shutil.copy2(str(src), str(dst))

        mat = Material(
            file_name=dst.name,
            file_type="video",
            file_size=dst.stat().st_size,
            file_path=str(dst),
            library_kind=library_kind,
            product_id=product_id,
            script_folder_id=script_folder_id,
        )
        db.add(mat)
        db.commit()
        db.refresh(mat)
        logger.info("[video_gen] task=%s promoted → material_id=%s path=%s", task_id, mat.id, dst)
        return mat.id
