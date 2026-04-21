from __future__ import annotations

import re
import threading
import time
from pathlib import Path

from ..config import Settings
from ..models.database import SessionLocal
from ..models.source_video_entry import SourceVideoEntry
from ..utils.file_utils import normalize_storage_path
from ..utils.logger import get_logger
from .subtitle_service import parse_srt


logger = get_logger()
_running_asr_entry_ids: set[int] = set()
_asr_lock = threading.Lock()
DEFAULT_ASR_RETRY_MAX = 3


def _normalize_asr_model(asr_model: str | None) -> str:
    value = (asr_model or "small").strip().lower()
    return value if value in {"small", "medium"} else "small"


def _normalize_retry_max(value: int | None) -> int:
    if value is None:
        return DEFAULT_ASR_RETRY_MAX
    try:
        parsed = int(value)
    except Exception:
        return DEFAULT_ASR_RETRY_MAX
    return max(1, min(parsed, 10))


def _safe_srt_file_name(entry_name: str, fallback: str) -> str:
    base = (entry_name or "").strip()
    if not base:
        base = fallback
    base = re.sub(r'[\\/:*?"<>|]+', "_", base)
    base = re.sub(r"\s+", " ", base).strip().strip(".")
    if not base:
        base = fallback
    base = Path(base).stem or base
    return f"{base}.srt"


def schedule_asr_for_source_entry(
    settings: Settings,
    *,
    source_entry_id: int,
    asr_model: str | None,
    force_retry: bool = False,
) -> None:
    model_name = _normalize_asr_model(asr_model)
    db = SessionLocal()
    try:
        entry = db.query(SourceVideoEntry).filter(SourceVideoEntry.id == source_entry_id).first()
        if not entry:
            return
        entry.asr_retry_max = _normalize_retry_max(entry.asr_retry_max)
        if force_retry:
            entry.asr_retry_count = 0
            entry.asr_status = "pending"
            entry.asr_error = None
        db.commit()
    finally:
        db.close()

    with _asr_lock:
        if source_entry_id in _running_asr_entry_ids:
            return
        _running_asr_entry_ids.add(source_entry_id)

    thread = threading.Thread(
        target=_run_asr_job,
        args=(settings, source_entry_id, model_name),
        daemon=True,
    )
    thread.start()


def _run_asr_job(settings: Settings, source_entry_id: int, asr_model: str) -> None:
    db = SessionLocal()
    try:
        entry = db.query(SourceVideoEntry).filter(SourceVideoEntry.id == source_entry_id).first()
        if not entry:
            return

        retry_max = _normalize_retry_max(entry.asr_retry_max)
        entry.asr_retry_max = retry_max
        db.commit()

        while True:
            db.refresh(entry)
            if int(entry.asr_retry_count or 0) >= retry_max:
                entry.asr_status = "failed"
                if not entry.asr_error:
                    entry.asr_error = "ASR 重试次数已达上限"
                db.commit()
                break

            entry.asr_status = "running"
            entry.asr_error = None
            entry.asr_model_used = asr_model
            db.commit()

            try:
                audio_path = entry.audio_flac_path or entry.audio_wav_path
                if not audio_path:
                    raise RuntimeError("未找到可用音轨文件")
                if not Path(audio_path).exists():
                    raise RuntimeError("音轨文件不存在")

                segments = transcribe_audio_segments(audio_path=audio_path, model_name=asr_model)

                output_file_name = _safe_srt_file_name(entry.name, f"source_{entry.id}")
                output_path = (
                    settings.data_dir
                    / "uploads"
                    / "subtitles"
                    / "asr"
                    / f"entry_{entry.id}"
                    / output_file_name
                )
                write_segments_to_srt(output_path=output_path, segments=segments)
                parsed = parse_srt(str(output_path), encoding="utf-8", time_offset_seconds=0.0)

                entry.asr_srt_path = normalize_storage_path(output_path)
                entry.subtitle_line_count_asr = len(parsed)
                entry.asr_status = "completed"
                entry.asr_error = None
                db.commit()
                break
            except Exception as exc:
                logger.exception("ASR failed for source entry {}: {}", source_entry_id, exc)
                db.refresh(entry)
                entry.asr_retry_count = int(entry.asr_retry_count or 0) + 1

                if entry.asr_retry_count < retry_max:
                    entry.asr_status = "pending"
                    entry.asr_error = (
                        f"第 {entry.asr_retry_count}/{retry_max} 次识别失败，准备自动重试: {str(exc)[:300]}"
                    )
                    db.commit()
                    sleep_seconds = min(2 ** entry.asr_retry_count, 10)
                    time.sleep(sleep_seconds)
                    continue

                entry.asr_status = "failed"
                entry.asr_error = str(exc)[:1000]
                db.commit()
                break
    finally:
        with _asr_lock:
            _running_asr_entry_ids.discard(source_entry_id)
        db.close()


def resume_pending_asr_jobs(settings: Settings) -> int:
    db = SessionLocal()
    scheduled = 0
    try:
        entries = db.query(SourceVideoEntry).all()
        for entry in entries:
            retry_max = _normalize_retry_max(entry.asr_retry_max)
            retry_count = int(entry.asr_retry_count or 0)
            has_asr_file = bool(entry.asr_srt_path and Path(entry.asr_srt_path).exists())
            status = (entry.asr_status or "pending").lower()

            should_resume = False
            if status in {"pending", "running"} and not has_asr_file:
                should_resume = True
            elif status == "failed" and retry_count < retry_max:
                should_resume = True

            if not should_resume:
                continue

            schedule_asr_for_source_entry(
                settings,
                source_entry_id=entry.id,
                asr_model=entry.asr_model_used or "small",
                force_retry=False,
            )
            scheduled += 1
        return scheduled
    finally:
        db.close()


def transcribe_audio_segments(*, audio_path: str, model_name: str) -> list[dict]:
    try:
        from faster_whisper import WhisperModel
    except Exception as exc:  # pragma: no cover - import failure branch
        raise RuntimeError("faster-whisper 未安装或加载失败") from exc

    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(audio_path, vad_filter=True)

    normalized: list[dict] = []
    for segment in segments:
        text = (getattr(segment, "text", "") or "").strip()
        if not text:
            continue
        start = max(0.0, float(getattr(segment, "start", 0.0) or 0.0))
        end = max(start + 0.01, float(getattr(segment, "end", start + 0.01) or (start + 0.01)))
        normalized.append({"start": start, "end": end, "text": text})
    return normalized


def _format_srt_time(seconds: float) -> str:
    total_ms = max(0, int(round(seconds * 1000)))
    hours = total_ms // 3_600_000
    minutes = (total_ms % 3_600_000) // 60_000
    secs = (total_ms % 60_000) // 1000
    millis = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def write_segments_to_srt(*, output_path: Path, segments: list[dict]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file_handle:
        for idx, seg in enumerate(segments, start=1):
            file_handle.write(f"{idx}\n")
            file_handle.write(
                f"{_format_srt_time(seg['start'])} --> {_format_srt_time(seg['end'])}\n"
            )
            file_handle.write(f"{seg['text']}\n\n")
