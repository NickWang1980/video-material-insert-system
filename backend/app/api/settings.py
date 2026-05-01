from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import Settings
from ..dependencies import get_app_settings, get_db
from ..schemas.settings import (
    AsrInstallCancelResponse,
    AsrInstallProgressResponse,
    AsrInstallStartResponse,
    AsrInstalledModelInfo,
    AsrModelCheckRequest,
    AsrModelCheckResponse,
    AsrModelDeleteRequest,
    AsrModelDeleteResponse,
    CacheCategoryInfo,
    CacheClearItemResult,
    CacheClearRequest,
    CacheClearResponse,
    FfmpegBinaryInfo,
    FfmpegInfoResponse,
    QueueClearResponse,
    QueueItem,
    QueueListResponse,
    SettingsResponse,
    SettingsUpdateRequest,
)
from ..services.asr_install_service import (
    cancel_install,
    delete_model,
    diagnose_model,
    get_model_size_mb,
    get_progress,
    list_installed_models,
    start_install,
)
from ..services.cache_service import clear_cache, list_cache_categories
from ..services.ffmpeg_service import get_ffmpeg_info, get_ffprobe_info
from ..services.queue_admin_service import (
    clear_asr_queue,
    clear_ffmpeg_queue,
    list_asr_queue,
    list_ffmpeg_queue,
)
from ..utils.encoder_utils import get_active_codec
from ..services.asr_service import _normalize_asr_model
from ..services.task_service import ensure_settings_row


router = APIRouter(prefix="/api/settings", tags=["settings"])


def _serialize(row) -> SettingsResponse:
    return SettingsResponse(
        output_format=row.output_format,
        resolution=row.resolution,
        video_bitrate_kbps=row.video_bitrate_kbps,
        subtitle_encoding=row.subtitle_encoding,
        subtitle_time_offset_seconds=float(row.subtitle_time_offset_seconds),
        asr_model=row.asr_model,
        asr_compute_type=getattr(row, "asr_compute_type", "auto") or "auto",
        video_encoder_mode=getattr(row, "video_encoder_mode", "auto") or "auto",
    )


@router.get("", response_model=SettingsResponse)
async def get_settings_endpoint(db: Session = Depends(get_db)):
    row = ensure_settings_row(db)
    return _serialize(row)


@router.put("", response_model=SettingsResponse)
async def update_settings(payload: SettingsUpdateRequest, db: Session = Depends(get_db)):
    row = ensure_settings_row(db)
    row.output_format = payload.output_format
    row.resolution = payload.resolution
    row.video_bitrate_kbps = payload.video_bitrate_kbps
    row.subtitle_encoding = payload.subtitle_encoding
    row.subtitle_time_offset_seconds = payload.subtitle_time_offset_seconds
    row.asr_model = payload.asr_model
    row.asr_compute_type = payload.asr_compute_type
    row.video_encoder_mode = payload.video_encoder_mode
    db.commit()
    db.refresh(row)
    return _serialize(row)


@router.post("/asr-model/check", response_model=AsrModelCheckResponse)
async def api_asr_model_check(
    payload: AsrModelCheckRequest,
    settings: Settings = Depends(get_app_settings),
):
    model = _normalize_asr_model(payload.model)
    ok, reason = diagnose_model(model, settings.data_dir)
    return AsrModelCheckResponse(
        model=model,
        installed=ok,
        size_mb=get_model_size_mb(model),
        reason=None if ok else reason,
    )


@router.post("/asr-model/install", response_model=AsrInstallStartResponse)
async def api_asr_model_install(
    payload: AsrModelCheckRequest,
    settings: Settings = Depends(get_app_settings),
):
    model = _normalize_asr_model(payload.model)
    task_id = start_install(model, settings.data_dir)
    return AsrInstallStartResponse(task_id=task_id)


@router.get(
    "/asr-model/install-progress/{task_id}",
    response_model=AsrInstallProgressResponse,
)
async def api_asr_install_progress(task_id: str):
    info = get_progress(task_id)
    if not info:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return AsrInstallProgressResponse(**info)


@router.post(
    "/asr-model/install/{task_id}/cancel",
    response_model=AsrInstallCancelResponse,
)
async def api_asr_install_cancel(task_id: str):
    ok, message = cancel_install(task_id)
    return AsrInstallCancelResponse(ok=ok, message=message)


@router.get("/asr-models", response_model=list[AsrInstalledModelInfo])
async def api_list_asr_models(settings: Settings = Depends(get_app_settings)):
    return [AsrInstalledModelInfo(**item) for item in list_installed_models(settings.data_dir)]


@router.delete("/asr-models", response_model=AsrModelDeleteResponse)
async def api_delete_asr_model(
    payload: AsrModelDeleteRequest,
    settings: Settings = Depends(get_app_settings),
):
    result = delete_model(
        payload.model,
        settings.data_dir,
        include_hf_cache=payload.include_hf_cache,
    )
    return AsrModelDeleteResponse(**{
        k: v for k, v in result.items() if k in {
            "model", "local_deleted", "local_path",
            "hf_cache_deleted", "hf_cache_path",
        }
    })


@router.get("/cache-info", response_model=list[CacheCategoryInfo])
async def api_cache_info(settings: Settings = Depends(get_app_settings)):
    cats = list_cache_categories(settings.data_dir)
    return [
        CacheCategoryInfo(
            key=c.key,
            label=c.label,
            description=c.description,
            safe=c.safe,
            paths=c.paths,
            size_bytes=c.size_bytes,
            file_count=c.file_count,
        )
        for c in cats
    ]


@router.post("/cache-clear", response_model=CacheClearResponse)
async def api_cache_clear(
    payload: CacheClearRequest,
    settings: Settings = Depends(get_app_settings),
):
    raw = clear_cache(settings.data_dir, payload.categories)
    summary = {k: CacheClearItemResult(**v) for k, v in raw.items()}
    total_b = sum(item.freed_bytes for item in summary.values())
    total_f = sum(item.freed_files for item in summary.values())
    return CacheClearResponse(
        summary=summary,
        total_freed_bytes=total_b,
        total_freed_files=total_f,
    )


@router.get("/ffmpeg-info", response_model=FfmpegInfoResponse)
async def api_ffmpeg_info(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
):
    ff_info = get_ffmpeg_info(settings.ffmpeg_bin)
    fp_info = get_ffprobe_info(settings.ffprobe_bin)
    row = ensure_settings_row(db)
    encoder_mode = getattr(row, "video_encoder_mode", "auto") or "auto"
    return FfmpegInfoResponse(
        ffmpeg=FfmpegBinaryInfo(**{k: ff_info[k] for k in FfmpegBinaryInfo.model_fields.keys()}),
        ffprobe=FfmpegBinaryInfo(**{k: fp_info[k] for k in FfmpegBinaryInfo.model_fields.keys()}),
        ffmpeg_configuration=ff_info.get("configuration", ""),
        hw_encoders=ff_info.get("hw_encoders", []),
        encoder_active=get_active_codec(encoder_mode, settings.ffmpeg_bin) if ff_info.get("ok") else "",
    )


# ── 队列管理 ────────────────────────────────────────────────────────────
@router.get("/asr-queue", response_model=QueueListResponse)
async def api_asr_queue():
    data = list_asr_queue()
    return QueueListResponse(
        items=[QueueItem(**i) for i in data["items"]],
        pending_count=data["pending_count"],
        running_count=data["running_count"],
        total_count=data["total_count"],
    )


@router.post("/asr-queue/clear", response_model=QueueClearResponse)
async def api_asr_queue_clear():
    data = clear_asr_queue()
    return QueueClearResponse(
        cancelled_source_count=data["cancelled_source_count"],
        cancelled_rough_cut_count=data["cancelled_rough_cut_count"],
        total_cancelled=data["total_cancelled"],
        note=data["note"],
    )


@router.get("/ffmpeg-queue", response_model=QueueListResponse)
async def api_ffmpeg_queue():
    data = list_ffmpeg_queue()
    return QueueListResponse(
        items=[QueueItem(**i) for i in data["items"]],
        pending_count=data["pending_count"],
        running_count=data["running_count"],
        total_count=data["total_count"],
    )


@router.post("/ffmpeg-queue/clear", response_model=QueueClearResponse)
async def api_ffmpeg_queue_clear():
    data = clear_ffmpeg_queue()
    return QueueClearResponse(
        stopped_task_count=data["stopped_task_count"],
        stopped_rough_cut_count=data["stopped_rough_cut_count"],
        total_stopped=data["total_stopped"],
        note=data["note"],
    )
