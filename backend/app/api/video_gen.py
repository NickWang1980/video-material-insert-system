"""Video Gen REST endpoints (mounted under /api/video-gen).

Phase-1 surfaces:
    GET    /api/video-gen/health
    POST   /api/video-gen                (multipart — files + json metadata)
    GET    /api/video-gen                (list — limit/offset)
    GET    /api/video-gen/{id}           (detail)
    POST   /api/video-gen/{id}/cancel
    GET    /api/video-gen/{id}/download
    POST   /api/video-gen/{id}/save-to-material

The POST create accepts up to two optional file fields (audio_file, video_file)
and a json `payload` form field describing source-type + source-ref. This
mirrors the multipart pattern used by the materials uploader.
"""
from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from ..config import Settings
from ..dependencies import get_app_settings
from ..models.database import SessionLocal
from ..models.video_gen import VideoGenTask
from ..schemas.video_gen import (
    VideoGenCreateRequest,
    VideoGenHealthResponse,
    VideoGenListResponse,
    VideoGenSaveToMaterialRequest,
    VideoGenSaveToMaterialResponse,
    VideoGenTaskResponse,
)
from ..services import video_gen_service


logger = logging.getLogger("app.api.video_gen")
router = APIRouter(prefix="/api/video-gen", tags=["video-gen"])


_ALLOWED_AUDIO_EXTS = frozenset({".wav", ".mp3", ".flac", ".m4a", ".ogg"})
_ALLOWED_VIDEO_EXTS = frozenset({".mp4", ".mov", ".mkv", ".avi", ".webm"})
_MAX_AUDIO_BYTES = 100 * 1024 * 1024   # 100 MB
_MAX_VIDEO_BYTES = 1024 * 1024 * 1024  # 1 GB


def _save_upload(
    upload: UploadFile,
    dest_dir: Path,
    allowed_exts: frozenset[str],
    max_bytes: int,
    field: str,
) -> Path:
    if not upload.filename:
        raise HTTPException(400, f"{field}: empty filename")
    ext = Path(upload.filename).suffix.lower()
    if ext not in allowed_exts:
        raise HTTPException(400, f"{field}: extension '{ext}' not allowed (need {sorted(allowed_exts)})")
    dest_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(upload.filename).stem.replace(" ", "_")[:80]
    dst = dest_dir / f"{uuid.uuid4().hex[:8]}_{stem}{ext}"
    written = 0
    with dst.open("wb") as f:
        while True:
            chunk = upload.file.read(1 << 20)
            if not chunk:
                break
            written += len(chunk)
            if written > max_bytes:
                dst.unlink(missing_ok=True)
                raise HTTPException(400, f"{field}: exceeds {max_bytes // (1024 * 1024)} MB limit")
            f.write(chunk)
    return dst


@router.get("/health", response_model=VideoGenHealthResponse)
def health(settings: Settings = Depends(get_app_settings)) -> VideoGenHealthResponse:
    data = video_gen_service.get_health(settings)
    return VideoGenHealthResponse(**data)


@router.post("/heygem/start")
def start_heygem(settings: Settings = Depends(get_app_settings)):
    """Spawn vendor/heygem/start_api.bat in a new detached cmd console.

    Used by the /video-gen page's "启动 heygem" button (visible in manual VRAM mode
    when heygem is not yet reachable). Idempotent: if /health is already up, returns
    `already_running=True` without spawning.
    """
    result = video_gen_service.start_heygem_sidecar(settings)
    if not result.get("started") and not result.get("already_running"):
        # Bubble up actionable error to the UI; 500 is too harsh for "bat missing"
        raise HTTPException(409, result.get("detail") or "failed to start heygem")
    return result


@router.post("", response_model=VideoGenTaskResponse)
def create(
    payload: str = Form(..., description="JSON-encoded VideoGenCreateRequest"),
    audio_file: Optional[UploadFile] = File(None),
    video_file: Optional[UploadFile] = File(None),
    settings: Settings = Depends(get_app_settings),
) -> VideoGenTaskResponse:
    try:
        req_dict = json.loads(payload)
    except Exception as exc:
        raise HTTPException(400, f"invalid payload JSON: {exc}")
    try:
        req = VideoGenCreateRequest(**req_dict)
    except Exception as exc:
        raise HTTPException(400, f"invalid payload schema: {exc}")

    if not settings.heygem_enabled:
        raise HTTPException(503, "heygem is disabled via settings (HEYGEM_ENABLED=0)")

    audio_uploaded: Optional[Path] = None
    if req.audio_source_type == "upload":
        if audio_file is None:
            raise HTTPException(400, "audio_source_type=upload requires audio_file multipart field")
        audio_uploaded = _save_upload(
            audio_file,
            settings.data_dir / "uploads" / "video_gen" / "audio",
            _ALLOWED_AUDIO_EXTS,
            _MAX_AUDIO_BYTES,
            "audio_file",
        )
    video_uploaded: Optional[Path] = None
    if req.video_source_type == "upload":
        if video_file is None:
            raise HTTPException(400, "video_source_type=upload requires video_file multipart field")
        video_uploaded = _save_upload(
            video_file,
            settings.data_dir / "uploads" / "video_gen" / "video",
            _ALLOWED_VIDEO_EXTS,
            _MAX_VIDEO_BYTES,
            "video_file",
        )

    try:
        task = video_gen_service.create_task(
            settings,
            task_name=req.task_name,
            audio_source_type=req.audio_source_type,
            audio_source_ref=req.audio_source_ref,
            audio_uploaded=audio_uploaded,
            video_source_type=req.video_source_type,
            video_source_ref=req.video_source_ref,
            video_uploaded=video_uploaded,
        )
    except video_gen_service.SourceResolutionError as exc:
        raise HTTPException(400, str(exc))
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))
    return VideoGenTaskResponse.model_validate(task)


@router.get("", response_model=VideoGenListResponse)
def list_tasks(
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> VideoGenListResponse:
    with SessionLocal() as db:
        total = db.query(VideoGenTask).count()
        items = (
            db.query(VideoGenTask)
            .order_by(VideoGenTask.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )
        return VideoGenListResponse(
            items=[VideoGenTaskResponse.model_validate(t) for t in items],
            total=total,
            limit=limit,
            offset=offset,
        )


@router.get("/{task_id}", response_model=VideoGenTaskResponse)
def detail(task_id: int) -> VideoGenTaskResponse:
    with SessionLocal() as db:
        t = db.get(VideoGenTask, task_id)
        if t is None:
            raise HTTPException(404, "task not found")
        return VideoGenTaskResponse.model_validate(t)


@router.post("/{task_id}/cancel")
def cancel(task_id: int):
    ok = video_gen_service.cancel_task(task_id)
    if not ok:
        raise HTTPException(409, "task not cancellable (already terminal or not found)")
    return {"message": "cancelled"}


@router.get("/{task_id}/download")
def download(task_id: int):
    with SessionLocal() as db:
        t = db.get(VideoGenTask, task_id)
        if t is None:
            raise HTTPException(404, "task not found")
        if t.status != "succeeded" or not t.result_path:
            raise HTTPException(409, f"task not ready (status={t.status})")
        p = Path(t.result_path)
        if not p.exists():
            raise HTTPException(410, "result file missing")
        return FileResponse(path=str(p), media_type="video/mp4", filename=p.name)


@router.post("/{task_id}/save-to-material", response_model=VideoGenSaveToMaterialResponse)
def save_to_material(
    task_id: int,
    body: VideoGenSaveToMaterialRequest,
    settings: Settings = Depends(get_app_settings),
) -> VideoGenSaveToMaterialResponse:
    try:
        mat_id = video_gen_service.save_to_material_library(
            task_id,
            settings,
            library_kind=body.library_kind,
            product_id=body.product_id,
            script_folder_id=body.script_folder_id,
            display_name=body.display_name,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return VideoGenSaveToMaterialResponse(material_id=mat_id, message="saved to material library")
