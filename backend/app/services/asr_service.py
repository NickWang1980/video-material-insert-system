from __future__ import annotations

import json
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
_opencc_converter = None

# HuggingFace repo IDs per model size used by faster-whisper / CTranslate2.
ASR_MODEL_REPOS: dict[str, str] = {
    "small":          "Systran/faster-whisper-small",
    "medium":         "Systran/faster-whisper-medium",
    "large-v3":       "Systran/faster-whisper-large-v3",
    "large-v3-turbo": "deepdml/faster-whisper-large-v3-turbo-ct2",
}

# Approximate download size (MB) — used for the install confirmation dialog.
ASR_MODEL_SIZES_MB: dict[str, int] = {
    "small": 480,
    "medium": 1500,
    "large-v3": 3100,
    "large-v3-turbo": 1620,
}

# Shared WhisperModel cache — keyed by (resolved_path_or_name, device, compute_type).
_whisper_model_cache: dict[tuple, object] = {}
_whisper_loading_events: dict[tuple, threading.Event] = {}
_whisper_model_cache_lock = threading.Lock()

# CUDA availability is probed once per process.
_cuda_available_cache: bool | None = None


def _detect_cuda_available() -> bool:
    global _cuda_available_cache
    if _cuda_available_cache is not None:
        return _cuda_available_cache
    try:
        import ctranslate2  # type: ignore
        _cuda_available_cache = ctranslate2.get_cuda_device_count() > 0
    except Exception:
        _cuda_available_cache = False
    logger.info(f"ASR CUDA available: {_cuda_available_cache}")
    return _cuda_available_cache


def _resolve_device_compute(compute_pref: str | None) -> tuple[str, str]:
    """Resolve user's compute preference to (device, compute_type) for WhisperModel.

    compute_pref: "auto" | "int8" | "float16" | "float32"
    规则：
      - int8 始终走 CPU，绝不与 CUDA 混用（int8_float16 在 CUDA 上质量与速度
        都不如纯 float16，反而失去 int8 的内存优势——属于劣解）。
      - float16 / float32 优先走 CUDA，CUDA 不可用时回退 CPU。
      - auto：有 CUDA 用 float16，无 CUDA 用 int8（CPU 上最快）。
    """
    has_cuda = _detect_cuda_available()
    pref = (compute_pref or "auto").strip().lower()

    # int8 显式选择 → 强制 CPU（不与 CUDA 混用）
    if pref == "int8":
        return "cpu", "int8"

    if has_cuda:
        if pref == "float32":
            return "cuda", "float32"
        # auto / float16 → float16 on GPU is the sweet spot
        return "cuda", "float16"

    # CPU 回退
    if pref == "float32":
        return "cpu", "float32"
    return "cpu", "int8"


def resolved_compute_label(compute_pref: str | None) -> str:
    """Human-readable string of the actually used compute_type + device.

    Example outputs:
        "int8 (CPU)"      — int8 selected (always CPU), or auto/float16 with no CUDA
        "float16 (CUDA)"  — auto/float16 selected with NVIDIA
        "float32 (CUDA)"  — float32 selected with NVIDIA
        "float32 (CPU)"   — float32 selected, no CUDA
    """
    device, compute_type = _resolve_device_compute(compute_pref)
    return f"{compute_type} ({device.upper()})"


def _get_or_load_whisper_model(model_name_or_path: str, compute_pref: str | None = None):
    device, compute_type = _resolve_device_compute(compute_pref)
    cache_key = (model_name_or_path, device, compute_type)

    with _whisper_model_cache_lock:
        if cache_key in _whisper_model_cache:
            return _whisper_model_cache[cache_key]
        if cache_key in _whisper_loading_events:
            event = _whisper_loading_events[cache_key]
            should_load = False
        else:
            event = threading.Event()
            _whisper_loading_events[cache_key] = event
            should_load = True

    if not should_load:
        event.wait()
        with _whisper_model_cache_lock:
            if cache_key in _whisper_model_cache:
                return _whisper_model_cache[cache_key]
        raise RuntimeError(f"ASR 模型 {model_name_or_path!r} 加载失败，请重试")

    try:
        from faster_whisper import WhisperModel
    except Exception as exc:
        with _whisper_model_cache_lock:
            _whisper_loading_events.pop(cache_key, None)
        event.set()
        raise RuntimeError("faster-whisper 未安装或加载失败") from exc

    try:
        logger.info(
            f"Loading WhisperModel: model={model_name_or_path} device={device} compute_type={compute_type}"
        )
        model = WhisperModel(model_name_or_path, device=device, compute_type=compute_type)
    except Exception:
        with _whisper_model_cache_lock:
            _whisper_loading_events.pop(cache_key, None)
        event.set()
        raise

    with _whisper_model_cache_lock:
        _whisper_model_cache[cache_key] = model
        _whisper_loading_events.pop(cache_key, None)
    event.set()
    return model


def get_loaded_asr_models() -> list[str]:
    with _whisper_model_cache_lock:
        return [str(k[0]) for k in _whisper_model_cache.keys()]


def _normalize_asr_model(asr_model: str | None) -> str:
    value = (asr_model or "small").strip().lower()
    return value if value in ASR_MODEL_REPOS else "small"


# ── ASR 模型完整性校验 ──────────────────────────────────────────────────────
# faster-whisper / CTranslate2 模型必备文件清单。`model.bin` 体积下限设 1 MB，
# 用于过滤 0 字节占位 / 截断下载这类常见失败。
ASR_MODEL_BIN_MIN_BYTES = 1 * 1024 * 1024
_ASR_TOKENIZER_CANDIDATES = ("tokenizer.json", "vocabulary.txt", "vocab.json")


def model_dir_for(model_name: str, data_dir: Path) -> Path:
    return data_dir / "asr_models" / f"faster-whisper-{_normalize_asr_model(model_name)}"


def check_model_integrity(model_name: str, data_dir: Path) -> tuple[bool, str | None]:
    """完整性检查：返回 (ok, reason)。reason 在 ok=False 时给出原因，便于诊断。"""
    local_dir = model_dir_for(model_name, data_dir)
    if not local_dir.is_dir():
        return False, "模型目录不存在"

    bin_file = local_dir / "model.bin"
    if not bin_file.exists():
        return False, "缺少 model.bin"
    try:
        bin_size = bin_file.stat().st_size
    except OSError as e:
        return False, f"无法读取 model.bin: {e}"
    if bin_size < ASR_MODEL_BIN_MIN_BYTES:
        return False, f"model.bin 体积异常（{bin_size} 字节，疑似下载中断）"

    cfg_file = local_dir / "config.json"
    if not cfg_file.exists() or cfg_file.stat().st_size == 0:
        return False, "缺少或损坏的 config.json"

    has_tokenizer = any(
        (local_dir / f).exists() and (local_dir / f).stat().st_size > 0
        for f in _ASR_TOKENIZER_CANDIDATES
    )
    if not has_tokenizer:
        return False, f"缺少分词器文件（{' / '.join(_ASR_TOKENIZER_CANDIDATES)} 任一）"

    return True, None


def is_model_complete(model_name: str, data_dir: Path) -> bool:
    ok, _ = check_model_integrity(model_name, data_dir)
    return ok


def _resolve_model_path(model_name: str, data_dir: Path) -> str:
    if is_model_complete(model_name, data_dir):
        return str(model_dir_for(model_name, data_dir))
    return model_name


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
            entry.asr_progress = 0
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
                entry.asr_progress = 100
                if not entry.asr_error:
                    entry.asr_error = "ASR 重试次数已达上限"
                db.commit()
                break

            entry.asr_status = "running"
            entry.asr_progress = max(35, int(entry.asr_progress or 0))
            entry.asr_error = None
            entry.asr_model_used = asr_model
            db.commit()

            try:
                audio_path = entry.audio_flac_path or entry.audio_wav_path
                if not audio_path:
                    raise RuntimeError("未找到可用音轨文件")
                if not Path(audio_path).exists():
                    raise RuntimeError("音轨文件不存在")

                entry.asr_progress = 45
                db.commit()
                model_path = _resolve_model_path(asr_model, settings.data_dir)
                from ..models.settings import SettingsRow as _SettingsRow
                _row = db.query(_SettingsRow).filter(_SettingsRow.id == 1).first()
                compute_pref = getattr(_row, "asr_compute_type", "auto") if _row else "auto"
                entry.asr_compute_type_used = resolved_compute_label(compute_pref)
                db.commit()
                segments = transcribe_audio_segments(
                    audio_path=audio_path, model_name=model_path, compute_pref=compute_pref
                )
                entry.asr_progress = 75
                db.commit()

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
                write_words_to_json(srt_path=output_path, segments=segments)
                entry.asr_progress = 90
                db.commit()
                parsed = parse_srt(str(output_path), encoding="utf-8", time_offset_seconds=0.0)

                entry.asr_srt_path = normalize_storage_path(output_path)
                entry.subtitle_line_count_asr = len(parsed)
                entry.asr_status = "completed"
                entry.asr_progress = 100
                entry.asr_error = None
                db.commit()
                break
            except Exception as exc:
                logger.exception("ASR failed for source entry {}: {}", source_entry_id, exc)
                db.refresh(entry)
                entry.asr_retry_count = int(entry.asr_retry_count or 0) + 1

                if entry.asr_retry_count < retry_max:
                    entry.asr_status = "pending"
                    entry.asr_progress = 10
                    entry.asr_error = (
                        f"第 {entry.asr_retry_count}/{retry_max} 次识别失败，准备自动重试: {str(exc)[:300]}"
                    )
                    db.commit()
                    sleep_seconds = min(2 ** entry.asr_retry_count, 10)
                    time.sleep(sleep_seconds)
                    continue

                entry.asr_status = "failed"
                entry.asr_progress = 100
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


def _get_opencc_converter():
    global _opencc_converter
    if _opencc_converter is not None:
        return _opencc_converter
    try:
        from opencc import OpenCC
    except Exception as exc:
        raise RuntimeError("ASR 简体转换依赖缺失，请安装 opencc-python-reimplemented") from exc
    _opencc_converter = OpenCC("t2s")
    return _opencc_converter


def _to_simplified_chinese(text: str) -> str:
    converter = _get_opencc_converter()
    return converter.convert(text)


def transcribe_audio_segments(
    *, audio_path: str, model_name: str, compute_pref: str | None = None
) -> list[dict]:
    model = _get_or_load_whisper_model(model_name, compute_pref=compute_pref)
    segments, _ = model.transcribe(
        audio_path,
        vad_filter=True,
        language="zh",
        task="transcribe",
        word_timestamps=True,
    )

    normalized: list[dict] = []
    for segment in segments:
        text = (getattr(segment, "text", "") or "").strip()
        if not text:
            continue
        text = _to_simplified_chinese(text)
        start = max(0.0, float(getattr(segment, "start", 0.0) or 0.0))
        end = max(start + 0.01, float(getattr(segment, "end", start + 0.01) or (start + 0.01)))
        words_data: list[dict] = []
        for w in getattr(segment, "words", None) or []:
            word_text = _to_simplified_chinese((w.word or "").strip())
            if word_text:
                words_data.append({
                    "word": word_text,
                    "start": max(0.0, float(w.start)),
                    "end": max(0.0, float(w.end)),
                })
        normalized.append({"start": start, "end": end, "text": text, "words": words_data})
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


def write_words_to_json(*, srt_path: Path, segments: list[dict]) -> None:
    all_words = sorted(
        [w for seg in segments for w in seg.get("words", [])],
        key=lambda x: x["start"],
    )
    words_path = srt_path.with_suffix(".words.json")
    words_path.write_text(
        json.dumps({"version": 1, "words": all_words}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
