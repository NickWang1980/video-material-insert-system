"""REST sidecar for the heygem digital-human engine.

Wraps `service.trans_dh_service.TransDhTask` so the master project
`video-material-insert-system` (running on a separate Python env) can
trigger digital-human synthesis over plain HTTP without touching the
embedded portable py39 or invoking the Gradio UI.

Endpoints (mounted under /api/heygem):
    POST   /synthesize         multipart: audio_file + video_file → {work_id}
    GET    /status/{work_id}   {phase, percent, completed, success, ...}
    GET    /result/{work_id}   FileResponse(mp4)  — only when completed=success
    GET    /health             {ready, gpu, version}

Run with the portable py39:
    start_api.bat     (sets env vars + uvicorn launch)

First-time deps install (only once, inside the portable env):
    py39\\python.exe -m pip install fastapi "uvicorn[standard]" python-multipart

Design notes
------------
* `TransDhTask.__init__` is HEAVY (loads wenet ~190 MB + spawns 2
  multiprocessing workers + opens 3 queues). We do it once at FastAPI
  startup so per-request latency is just the actual inference.
* `task.work(audio, video, code, 0, 0, 0, 1)` is SYNCHRONOUS; we wrap it
  in a per-request `threading.Thread` so /synthesize returns immediately
  with the work_id and the caller polls /status.
* `task.task_dic[code] = (Status, progress, result_path, msg)` is the
  heygem-internal state, written by `change_task_status`. A side watcher
  thread mirrors it into our `_states` dict in REST-friendly form.
* Audio is converted to 16k mono PCM via ffmpeg (matches the original
  Gradio path) — qwen TTS often emits 24k/44.1k.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
import traceback
import uuid
from pathlib import Path
from typing import Any, Optional

# Path bootstrap so module imports resolve regardless of cwd
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse


# --- Lazy/late imports so missing heavy deps don't break the API import ----
_task_instance: Any = None
_task_init_error: Optional[str] = None
_task_init_lock = threading.Lock()

AUDIO_DIR = BASE_DIR / "audio"
RESULT_DIR = BASE_DIR / "result"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
RESULT_DIR.mkdir(parents=True, exist_ok=True)


# --- Per-request state -----------------------------------------------------
# {work_id: {phase, percent, message, completed, success, result_path, error,
#            started_at, finished_at, audio_path, video_path}}
_states: dict[str, dict[str, Any]] = {}
_states_lock = threading.Lock()


def _set_state(work_id: str, **kwargs: Any) -> None:
    with _states_lock:
        s = _states.setdefault(work_id, {
            "phase": "queued",
            "percent": 0,
            "message": "",
            "completed": False,
            "success": False,
            "result_path": None,
            "error": None,
            "started_at": time.time(),
            "finished_at": None,
        })
        s.update(kwargs)


def _get_state(work_id: str) -> Optional[dict[str, Any]]:
    with _states_lock:
        return dict(_states[work_id]) if work_id in _states else None


# --- ffmpeg helper (mirrors app.py::convert_audio_to_16k) ------------------
def _convert_to_16k_mono(src: Path, dst: Path) -> None:
    cmd = [
        "ffmpeg", "-y", "-i", str(src),
        "-ac", "1", "-ar", "16000",
        "-acodec", "pcm_s16le",
        str(dst),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"ffmpeg 16k conversion failed: {res.stderr[-400:]}")


# --- TransDhTask singleton -------------------------------------------------
def _ensure_task() -> Any:
    global _task_instance, _task_init_error
    if _task_instance is not None:
        return _task_instance
    with _task_init_lock:
        if _task_instance is not None:
            return _task_instance
        try:
            # These imports are expensive — only at first use.
            import service.trans_dh_service as tds  # noqa: PLC0415
            _task_instance = tds.TransDhTask()
            _task_init_error = None
            print("[heygem-api] TransDhTask initialized", flush=True)
        except Exception as exc:  # noqa: BLE001
            _task_init_error = f"{type(exc).__name__}: {exc}"
            traceback.print_exc()
            raise
        return _task_instance


# --- State mirror (heygem internal Status enum → REST phase/percent) -------
_PHASE_FROM_PERCENT = [
    (0, "queued"),
    (1, "preprocess"),
    (15, "audio_feature_extract"),
    (25, "face_detect_align"),
    (50, "render_frames"),
    (90, "video_encode"),
    (100, "done"),
]


def _phase_label(percent: int) -> str:
    label = "queued"
    for thr, name in _PHASE_FROM_PERCENT:
        if percent >= thr:
            label = name
    return label


def _watcher(work_id: str) -> None:
    """Mirror task.task_dic[code] -> _states[work_id] until terminal."""
    try:
        import service.trans_dh_service as tds  # noqa: PLC0415
        Status = tds.Status  # heygem-internal enum
    except Exception:
        return
    task = _task_instance
    while True:
        time.sleep(1.0)
        entry = task.task_dic.get(work_id, "")
        if not isinstance(entry, tuple):
            continue
        try:
            st, progress, result_path, msg = entry
        except ValueError:
            continue
        if st == Status.success:
            _set_state(
                work_id,
                phase="done",
                percent=100,
                message=msg,
                completed=True,
                success=True,
                result_path=str(result_path) if result_path else None,
                finished_at=time.time(),
            )
            return
        if st == Status.error:
            _set_state(
                work_id,
                phase="failed",
                percent=int(progress or 0),
                message=msg,
                completed=True,
                success=False,
                error=str(msg) or "unknown",
                finished_at=time.time(),
            )
            return
        # Running
        p = int(progress or 0)
        _set_state(
            work_id,
            phase=_phase_label(p),
            percent=p,
            message=msg,
        )


# --- FastAPI app -----------------------------------------------------------
app = FastAPI(title="heygem digital-human REST sidecar", version="phase-1")


@app.on_event("startup")
def _startup() -> None:
    # Kick off heavy init in background so /health responds quickly even
    # while wenet weights are loading.
    threading.Thread(target=_warmup, daemon=True, name="heygem-warmup").start()


def _warmup() -> None:
    try:
        _ensure_task()
    except Exception:
        pass  # logged by _ensure_task


@app.get("/api/heygem/health")
def health() -> JSONResponse:
    ready = _task_instance is not None
    gpu = ""
    try:
        import torch  # noqa: PLC0415
        gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else ""
    except Exception:
        gpu = ""
    return JSONResponse({
        "ready": ready,
        "gpu": gpu,
        "version": "phase-1",
        "init_error": _task_init_error,
    })


@app.post("/api/heygem/synthesize")
async def synthesize(
    audio_file: UploadFile = File(...),
    video_file: UploadFile = File(...),
) -> JSONResponse:
    if _task_instance is None and _task_init_error:
        raise HTTPException(503, f"heygem not ready: {_task_init_error}")
    # Ensure task is initialized (may still be warming up — block briefly)
    deadline = time.time() + 60
    while _task_instance is None:
        if time.time() > deadline:
            raise HTTPException(503, "heygem still initializing; retry in a few seconds")
        time.sleep(1)

    work_id = uuid.uuid4().hex
    # Save audio
    in_audio = AUDIO_DIR / f"{work_id}_in{Path(audio_file.filename or '').suffix or '.wav'}"
    out_audio = AUDIO_DIR / f"{work_id}_16k.wav"
    with in_audio.open("wb") as f:
        while True:
            chunk = await audio_file.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    # Save video
    in_video = AUDIO_DIR / f"{work_id}_in{Path(video_file.filename or '').suffix or '.mp4'}"
    with in_video.open("wb") as f:
        while True:
            chunk = await video_file.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)

    try:
        _convert_to_16k_mono(in_audio, out_audio)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"audio conversion failed: {exc}")

    _set_state(work_id, phase="preprocess", percent=1, message="files staged")

    # Register code in heygem's task_dic so change_task_status can write it
    _task_instance.task_dic[work_id] = ""

    def _run() -> None:
        try:
            _task_instance.work(str(out_audio), str(in_video), work_id, 0, 0, 0, 1)
        except Exception as exc:  # noqa: BLE001
            _set_state(
                work_id,
                phase="failed",
                completed=True,
                success=False,
                error=f"{type(exc).__name__}: {exc}",
                finished_at=time.time(),
            )

    threading.Thread(target=_run, daemon=True, name=f"heygem-job-{work_id[:6]}").start()
    threading.Thread(target=_watcher, args=(work_id,), daemon=True, name=f"heygem-watch-{work_id[:6]}").start()

    return JSONResponse({"work_id": work_id})


@app.get("/api/heygem/status/{work_id}")
def status(work_id: str) -> JSONResponse:
    s = _get_state(work_id)
    if s is None:
        raise HTTPException(404, "unknown work_id")
    elapsed = time.time() - s["started_at"]
    return JSONResponse({**s, "elapsed_sec": int(elapsed)})


@app.get("/api/heygem/result/{work_id}")
def result(work_id: str):
    s = _get_state(work_id)
    if s is None:
        raise HTTPException(404, "unknown work_id")
    if not s["completed"]:
        raise HTTPException(409, "job not finished")
    if not s["success"]:
        raise HTTPException(409, f"job failed: {s.get('error')}")
    rp = s.get("result_path")
    if not rp or not Path(rp).is_file():
        raise HTTPException(410, "result file missing")
    return FileResponse(path=rp, media_type="video/mp4", filename=Path(rp).name)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8383)
