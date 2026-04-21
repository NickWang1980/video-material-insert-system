from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..config import Settings
from ..dependencies import get_app_settings, get_db
from ..models.source_video_entry import SourceVideoEntry
from ..models.task import Task
from ..schemas.common import MessageResponse
from ..schemas.source_video import (
    ParsedSubtitleResponse,
    SourceVideoEntryRenameRequest,
    SourceVideoEntryResponse,
)
from ..services.asr_service import schedule_asr_for_source_entry
from ..services.subtitle_service import parse_srt
from ..services.task_service import ensure_settings_row
from ..services.video_service import export_audio_track, probe_video
from ..utils.file_utils import normalize_storage_path


router = APIRouter(prefix="/api/source-videos", tags=["source-videos"])


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _default_entry_name() -> str:
    return f"源视频_{_timestamp()}"


def _gcd(a: int, b: int) -> int:
    while b:
        a, b = b, a % b
    return max(1, abs(a))


def _aspect_ratio_text(width: int, height: int) -> str:
    g = _gcd(width, height)
    return f"{width // g}:{height // g}"


def _save_upload_file(dst_path: Path, upload_file: UploadFile) -> None:
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    with dst_path.open("wb") as output:
        while True:
            chunk = upload_file.file.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)


def _entry_to_response(entry: SourceVideoEntry) -> SourceVideoEntryResponse:
    has_wav = bool(entry.audio_wav_path and Path(entry.audio_wav_path).exists())
    has_flac = bool(entry.audio_flac_path and Path(entry.audio_flac_path).exists())
    has_uploaded_srt = bool(entry.subtitle_path and Path(entry.subtitle_path).exists())
    has_asr_srt = bool(entry.asr_srt_path and Path(entry.asr_srt_path).exists())
    effective_asr_status = "completed" if has_asr_srt else (entry.asr_status or "pending")
    return SourceVideoEntryResponse(
        id=entry.id,
        name=entry.name,
        video_path=entry.video_path,
        subtitle_path=entry.subtitle_path,
        video_width=entry.video_width,
        video_height=entry.video_height,
        video_aspect_ratio=entry.video_aspect_ratio,
        audio_wav_path=entry.audio_wav_path,
        audio_flac_path=entry.audio_flac_path,
        asr_srt_path=entry.asr_srt_path,
        asr_status=effective_asr_status,
        asr_error=entry.asr_error,
        asr_retry_count=int(entry.asr_retry_count or 0),
        asr_retry_max=int(entry.asr_retry_max or 3),
        subtitle_line_count_user=entry.subtitle_line_count_user,
        subtitle_line_count_asr=entry.subtitle_line_count_asr,
        asr_model_used=entry.asr_model_used,
        has_wav=has_wav,
        has_flac=has_flac,
        has_uploaded_srt=has_uploaded_srt,
        has_asr_srt=has_asr_srt,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


def _get_entry_or_404(db: Session, entry_id: int) -> SourceVideoEntry:
    entry = db.query(SourceVideoEntry).filter(SourceVideoEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="源视频条目不存在")
    return entry


def _resolve_subtitle_path(
    entry: SourceVideoEntry, source: Literal["uploaded", "asr"]
) -> str:
    if source == "uploaded":
        if not entry.subtitle_path:
            raise HTTPException(status_code=404, detail="未上传 SRT 字幕")
        if not Path(entry.subtitle_path).exists():
            raise HTTPException(status_code=404, detail="上传 SRT 字幕文件不存在")
        return entry.subtitle_path

    if entry.asr_srt_path and Path(entry.asr_srt_path).exists():
        return entry.asr_srt_path

    asr_status = entry.asr_status or "pending"
    if asr_status != "completed":
        raise HTTPException(status_code=400, detail=f"ASR 字幕未就绪，当前状态: {asr_status}")
    raise HTTPException(status_code=404, detail="ASR 字幕不存在")


@router.post("", response_model=SourceVideoEntryResponse)
async def create_source_video_entry(
    name: str | None = Form(None),
    video: UploadFile = File(...),
    subtitle: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
):
    if subtitle is not None and not subtitle.filename.lower().endswith(".srt"):
        raise HTTPException(status_code=400, detail="字幕文件必须为 .srt")

    entry_name = (name or "").strip() or _default_entry_name()
    ts = _timestamp()
    video_filename = f"source_video_{ts}_{video.filename}"
    video_path = settings.data_dir / "uploads" / "videos" / video_filename

    subtitle_path: Path | None = None
    if subtitle is not None:
        subtitle_filename = f"source_subtitle_{ts}_{subtitle.filename}"
        subtitle_path = settings.data_dir / "uploads" / "subtitles" / subtitle_filename

    wav_path = settings.data_dir / "uploads" / "source_audio" / f"source_audio_{ts}.wav"
    flac_path = settings.data_dir / "uploads" / "source_audio" / f"source_audio_{ts}.flac"

    saved_paths: list[Path] = [video_path, wav_path, flac_path]
    if subtitle_path is not None:
        saved_paths.append(subtitle_path)

    _save_upload_file(video_path, video)
    if subtitle is not None and subtitle_path is not None:
        _save_upload_file(subtitle_path, subtitle)

    settings_row = ensure_settings_row(db)

    try:
        probe = probe_video(settings, str(video_path))
        export_audio_track(
            settings,
            video_path=str(video_path),
            output_path=str(wav_path),
            audio_format="wav",
        )
        export_audio_track(
            settings,
            video_path=str(video_path),
            output_path=str(flac_path),
            audio_format="flac",
        )
        parsed_user_subtitles = None
        if subtitle_path is not None:
            parsed_user_subtitles = parse_srt(
                str(subtitle_path),
                encoding=settings_row.subtitle_encoding,
                time_offset_seconds=0.0,
            )
    except Exception as exc:
        for path in saved_paths:
            try:
                if path.exists():
                    os.remove(path)
            except Exception:
                pass
        raise HTTPException(status_code=400, detail=f"创建源视频条目失败: {exc}") from exc

    entry = SourceVideoEntry(
        name=entry_name,
        video_path=normalize_storage_path(video_path),
        subtitle_path=normalize_storage_path(subtitle_path) if subtitle_path else "",
        video_width=int(probe.width),
        video_height=int(probe.height),
        video_aspect_ratio=_aspect_ratio_text(int(probe.width), int(probe.height)),
        audio_wav_path=normalize_storage_path(wav_path),
        audio_flac_path=normalize_storage_path(flac_path),
        asr_status="pending",
        asr_error=None,
        asr_retry_count=0,
        asr_retry_max=3,
        subtitle_line_count_user=(
            len(parsed_user_subtitles) if parsed_user_subtitles is not None else None
        ),
        subtitle_line_count_asr=None,
        asr_model_used=settings_row.asr_model,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    schedule_asr_for_source_entry(
        settings,
        source_entry_id=entry.id,
        asr_model=settings_row.asr_model,
    )
    db.refresh(entry)
    return _entry_to_response(entry)


@router.post("/{entry_id}/asr/retry", response_model=MessageResponse)
async def retry_source_video_asr(
    entry_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
):
    entry = _get_entry_or_404(db, entry_id)
    schedule_asr_for_source_entry(
        settings,
        source_entry_id=entry.id,
        asr_model=entry.asr_model_used or "small",
        force_retry=True,
    )
    return MessageResponse(message="已触发ASR重试")


@router.get("", response_model=list[SourceVideoEntryResponse])
async def list_source_video_entries(db: Session = Depends(get_db)):
    entries = db.query(SourceVideoEntry).order_by(SourceVideoEntry.id.desc()).all()
    return [_entry_to_response(entry) for entry in entries]


@router.put("/{entry_id}", response_model=SourceVideoEntryResponse)
async def rename_source_video_entry(
    entry_id: int,
    payload: SourceVideoEntryRenameRequest,
    db: Session = Depends(get_db),
):
    entry = _get_entry_or_404(db, entry_id)
    new_name = payload.name.strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="名称不能为空")

    entry.name = new_name
    db.commit()
    db.refresh(entry)
    return _entry_to_response(entry)


@router.get("/{entry_id}/audio")
async def download_source_audio(
    entry_id: int,
    format: Literal["wav", "flac"] = Query("wav"),
    db: Session = Depends(get_db),
):
    entry = _get_entry_or_404(db, entry_id)
    file_path = entry.audio_wav_path if format == "wav" else entry.audio_flac_path
    if not file_path or not Path(file_path).exists():
        raise HTTPException(status_code=404, detail=f"{format.upper()} 音轨不存在")
    return FileResponse(file_path, filename=Path(file_path).name)


@router.get("/{entry_id}/subtitle")
async def download_source_subtitle(
    entry_id: int,
    source: Literal["uploaded", "asr"] = Query("uploaded"),
    db: Session = Depends(get_db),
):
    entry = _get_entry_or_404(db, entry_id)
    file_path = _resolve_subtitle_path(entry, source)
    if not Path(file_path).exists():
        raise HTTPException(status_code=404, detail="字幕文件不存在")
    return FileResponse(file_path, filename=Path(file_path).name)


@router.get("/{entry_id}/subtitle/parsed", response_model=ParsedSubtitleResponse)
async def get_parsed_subtitle(
    entry_id: int,
    source: Literal["uploaded", "asr"] = Query("uploaded"),
    db: Session = Depends(get_db),
):
    entry = _get_entry_or_404(db, entry_id)
    subtitle_path = _resolve_subtitle_path(entry, source)
    if not Path(subtitle_path).exists():
        raise HTTPException(status_code=404, detail="字幕文件不存在")

    settings_row = ensure_settings_row(db)
    subtitle_encoding = "utf-8" if source == "asr" else settings_row.subtitle_encoding
    lines = parse_srt(subtitle_path, encoding=subtitle_encoding, time_offset_seconds=0.0)
    return ParsedSubtitleResponse(source=source, line_count=len(lines), lines=lines)


@router.delete("/{entry_id}", response_model=MessageResponse)
async def delete_source_video_entry(entry_id: int, db: Session = Depends(get_db)):
    entry = _get_entry_or_404(db, entry_id)

    referenced_count = db.query(Task).filter(Task.source_entry_id == entry_id).count()
    if referenced_count > 0:
        raise HTTPException(status_code=400, detail="该源视频条目已被任务引用，禁止删除")

    for file_path in [
        entry.video_path,
        entry.subtitle_path,
        entry.audio_wav_path,
        entry.audio_flac_path,
        entry.asr_srt_path,
    ]:
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass

    db.delete(entry)
    db.commit()
    return MessageResponse(message="源视频条目已删除")
