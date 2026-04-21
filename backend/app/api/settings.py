from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..dependencies import get_db
from ..schemas.settings import SettingsResponse, SettingsUpdateRequest
from ..services.task_service import ensure_settings_row


router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse)
async def get_settings(db: Session = Depends(get_db)):
    row = ensure_settings_row(db)
    return SettingsResponse(
        output_format=row.output_format,
        resolution=row.resolution,
        video_bitrate_kbps=row.video_bitrate_kbps,
        subtitle_encoding=row.subtitle_encoding,
        subtitle_time_offset_seconds=float(row.subtitle_time_offset_seconds),
        asr_model=row.asr_model,
    )


@router.put("", response_model=SettingsResponse)
async def update_settings(payload: SettingsUpdateRequest, db: Session = Depends(get_db)):
    row = ensure_settings_row(db)
    row.output_format = payload.output_format
    row.resolution = payload.resolution
    row.video_bitrate_kbps = payload.video_bitrate_kbps
    row.subtitle_encoding = payload.subtitle_encoding
    row.subtitle_time_offset_seconds = payload.subtitle_time_offset_seconds
    row.asr_model = payload.asr_model
    db.commit()
    db.refresh(row)
    return SettingsResponse(
        output_format=row.output_format,
        resolution=row.resolution,
        video_bitrate_kbps=row.video_bitrate_kbps,
        subtitle_encoding=row.subtitle_encoding,
        subtitle_time_offset_seconds=float(row.subtitle_time_offset_seconds),
        asr_model=row.asr_model,
    )
