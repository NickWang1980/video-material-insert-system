from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..config import Settings
from ..dependencies import get_app_settings
from ..schemas.common import MessageResponse
from ..utils.logger import get_logger


logger = get_logger()
from ..schemas.tts import (
    TTSEnumValue,
    TTSModelDeleteResponse,
    TTSModelInfo,
    TTSModelListResponse,
    TTSReferenceUploadResponse,
    TTSStatusResponse,
    TTSSynthesizeRequest,
    TTSSynthesizeResponse,
    TTSVoiceInfo,
)
from ..services import tts_service


router = APIRouter(prefix="/api/tts", tags=["tts"])


@router.get("/status", response_model=TTSStatusResponse)
def get_status() -> TTSStatusResponse:
    """Snapshot of TTS model loading state — frontend polls this every ~2 s."""
    s = tts_service.get_status()
    return TTSStatusResponse(
        phase=s.get("phase", "idle"),
        percent=int(s.get("percent", 0)),
        detail=str(s.get("detail", "")),
        message=str(s.get("message", "")),
        error=s.get("error"),
        elapsed_sec=int(s.get("elapsed_sec", 0)),
        ready=bool(s.get("ready", False)),
        base_loaded=bool(s.get("base_loaded", False)),
        custom_loaded=bool(s.get("custom_loaded", False)),
        loaded_models=list(s.get("loaded_models", [])),
    )


@router.post("/load", response_model=MessageResponse)
def trigger_load(settings: Settings = Depends(get_app_settings)) -> MessageResponse:
    """Manually preload the Base model in a background thread (non-blocking)."""
    import threading
    logger.info("[TTS][api] /load triggered model={}", tts_service.TTS_BASE_MODEL_ID)
    threading.Thread(
        target=lambda: tts_service.get_or_load_tts(tts_service.TTS_BASE_MODEL_ID, settings),
        daemon=True,
        name="tts-manual-load",
    ).start()
    return MessageResponse(message="Loading triggered in background")


@router.post("/load-custom", response_model=MessageResponse)
def trigger_load_custom(settings: Settings = Depends(get_app_settings)) -> MessageResponse:
    """Manually preload CustomVoice (settings.tts_custom_voice_enabled must be True)."""
    if not getattr(settings, "tts_custom_voice_enabled", False):
        logger.warning("[TTS][api] /load-custom rejected: CustomVoice disabled in settings")
        raise HTTPException(status_code=400, detail="CustomVoice is disabled in settings")
    import threading
    logger.info("[TTS][api] /load-custom triggered model={}", tts_service.TTS_CUSTOM_MODEL_ID)
    threading.Thread(
        target=lambda: tts_service.get_or_load_tts(tts_service.TTS_CUSTOM_MODEL_ID, settings),
        daemon=True,
        name="tts-manual-load-custom",
    ).start()
    return MessageResponse(message="CustomVoice load triggered in background")


@router.post("/unload", response_model=MessageResponse)
def trigger_unload() -> MessageResponse:
    """Drop every cached TTS model and free RAM (~7 GB per model)."""
    logger.info("[TTS][api] /unload triggered")
    n = tts_service.unload_all()
    logger.info("[TTS][api] /unload result count={}", n)
    return MessageResponse(message=f"Unloaded {n} model(s)")


@router.post("/synthesize", response_model=TTSSynthesizeResponse)
def synthesize(
    payload: TTSSynthesizeRequest,
    settings: Settings = Depends(get_app_settings),
) -> TTSSynthesizeResponse:
    """Text → speech. If model not ready, this call lazy-loads it (may block 30–90 s).

    If another request is already loading the same model (typical first session
    where a 1.7 GB download is in progress), return 503 + Retry-After so the
    caller can poll /api/tts/status instead of holding an ASGI worker thread
    for up to 15 minutes on a wait.
    """
    use_custom = bool(payload.voice and payload.voice in tts_service.PRESET_SPEAKERS)
    target_model_id = (
        tts_service.TTS_CUSTOM_MODEL_ID if use_custom else tts_service.TTS_BASE_MODEL_ID
    )
    logger.info(
        "[TTS][api] /synthesize text_len={} language={} voice={} emotion={} "
        "speed={} ref_audio={} target_model={}",
        len(payload.text or ""),
        payload.language,
        payload.voice,
        payload.emotion,
        payload.speed,
        bool(payload.ref_audio),
        target_model_id,
    )
    if tts_service.is_loading_in_progress(target_model_id, settings):
        logger.warning(
            "[TTS][api] /synthesize rejected: model still loading ({})", target_model_id
        )
        raise HTTPException(
            status_code=503,
            detail="TTS model is still loading; poll /api/tts/status and retry.",
            headers={"Retry-After": "5"},
        )
    try:
        rel_path, duration = tts_service.synthesize(
            settings,
            text=payload.text,
            language=payload.language,
            ref_audio=payload.ref_audio,
            voice=payload.voice,
            emotion=payload.emotion,
            speed=payload.speed,
            instruct=payload.instruct,
        )
    except ValueError as exc:
        logger.warning("[TTS][api] /synthesize bad input: {}", exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.exception("[TTS][api] /synthesize failed: {}", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    # Build a downloadable URL relative to the backend
    audio_url = f"/api/tts/audio/{Path(rel_path).name}"
    logger.info(
        "[TTS][api] /synthesize ok audio={} duration={:.2f}s", audio_url, duration
    )
    return TTSSynthesizeResponse(
        status="success",
        audio_url=audio_url,
        duration_sec=duration,
        message="Speech generated successfully",
    )


@router.get("/audio/{filename}")
def get_audio(filename: str, settings: Settings = Depends(get_app_settings)) -> FileResponse:
    """Stream a previously-generated TTS WAV by filename."""
    safe_name = Path(filename).name  # strip any path traversal
    target = settings.data_dir / "outputs" / "tts" / safe_name
    if not target.exists():
        raise HTTPException(status_code=404, detail="Audio not found")
    return FileResponse(path=str(target), media_type="audio/wav", filename=safe_name)


# Reference-audio upload guards
_ALLOWED_REF_EXTS = frozenset({".wav", ".mp3", ".flac", ".m4a", ".ogg"})
_MAX_REF_BYTES = 50 * 1024 * 1024  # 50 MB — voice samples are typically <2 MB


@router.post("/upload-reference", response_model=TTSReferenceUploadResponse)
async def upload_reference(
    audio: UploadFile = File(...),
    settings: Settings = Depends(get_app_settings),
) -> TTSReferenceUploadResponse:
    """Upload a reference audio (≥3 s, ≤50 MB) for voice cloning.

    Accepts wav/mp3/flac/m4a/ogg; preserves the original extension so qwen_tts
    can decode the file. Streams the upload with a hard size cap so a malicious
    or accidental huge file cannot fill the disk.
    """
    if not audio.filename:
        raise HTTPException(status_code=400, detail="Empty filename")
    ext = Path(audio.filename).suffix.lower()
    if ext not in _ALLOWED_REF_EXTS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported audio extension '{ext}'. "
                f"Allowed: {sorted(_ALLOWED_REF_EXTS)}"
            ),
        )
    ctype = (audio.content_type or "").lower()
    if ctype and not (ctype.startswith("audio/") or ctype == "application/octet-stream"):
        raise HTTPException(
            status_code=400,
            detail=f"Unexpected content-type '{ctype}'; expected audio/*",
        )

    ref_dir = settings.data_dir / "uploads" / "tts_refs"
    ref_dir.mkdir(parents=True, exist_ok=True)
    safe_stem = Path(audio.filename).stem.replace(" ", "_")[:80]
    dst = ref_dir / f"ref_{uuid.uuid4().hex[:8]}_{safe_stem}{ext}"

    written = 0
    try:
        with dst.open("wb") as out:
            while True:
                chunk = await audio.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > _MAX_REF_BYTES:
                    out.close()
                    dst.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Reference audio exceeds "
                            f"{_MAX_REF_BYTES // (1024 * 1024)} MB limit"
                        ),
                    )
                out.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        dst.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}")

    return TTSReferenceUploadResponse(
        status="success",
        ref_audio_path=str(dst),
        message="Reference audio uploaded",
    )


@router.get("/voices", response_model=list[TTSVoiceInfo])
def list_voices(settings: Settings = Depends(get_app_settings)) -> list[TTSVoiceInfo]:
    """Preset speaker names (only meaningful when CustomVoice is enabled+loaded)."""
    if not getattr(settings, "tts_custom_voice_enabled", False):
        return []
    return [TTSVoiceInfo(code=name) for name in tts_service.PRESET_SPEAKERS]


@router.get("/languages", response_model=list[TTSEnumValue])
def list_languages() -> list[TTSEnumValue]:
    return [TTSEnumValue(code=c, name=c) for c in tts_service.SUPPORTED_LANGUAGES]


@router.get("/emotions", response_model=list[TTSEnumValue])
def list_emotions() -> list[TTSEnumValue]:
    return [TTSEnumValue(code=c, name=c.capitalize()) for c in tts_service.SUPPORTED_EMOTIONS]


@router.get("/models", response_model=TTSModelListResponse)
def list_models(settings: Settings = Depends(get_app_settings)) -> TTSModelListResponse:
    """模型管理（Settings 页用）：列出 Base / CustomVoice 各自的缓存与加载状态。"""
    info = tts_service.list_models_info(settings)
    return TTSModelListResponse(
        models=[TTSModelInfo(**m) for m in info["models"]],
        cache_root=info["cache_root"],
    )


@router.delete("/models/{key}", response_model=TTSModelDeleteResponse)
def delete_model_endpoint(
    key: str,
    settings: Settings = Depends(get_app_settings),
) -> TTSModelDeleteResponse:
    """删除磁盘缓存（先 unload 内存中的实例）。key: base | custom"""
    if key not in tts_service.TTS_MODEL_KEYS:
        raise HTTPException(status_code=400, detail=f"Unknown model key: {key}")
    try:
        result = tts_service.delete_model_cache(settings, key)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc))
    return TTSModelDeleteResponse(**result)
