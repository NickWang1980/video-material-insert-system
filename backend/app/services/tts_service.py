"""
Qwen3-TTS lazy-loaded service for the FastAPI backend.

Mirrors the pattern of asr_service._whisper_model_cache:
    - shared in-process cache keyed by (model_id, device, dtype)
    - threading.Event for concurrent first-loaders
    - background watchdog that unloads idle models
"""
from __future__ import annotations

import gc
import os
import shutil
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from ..config import Settings
from ..utils.file_utils import normalize_storage_path
from ..utils.logger import get_logger
from ..utils.tqdm_progress_hook import install_progress_hook


logger = get_logger()

# ---- Model identifiers --------------------------------------------------
TTS_BASE_MODEL_ID = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
TTS_CUSTOM_MODEL_ID = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"

# Approximate sizes for the install-confirmation dialog
TTS_MODEL_SIZES_MB: dict[str, int] = {
    TTS_BASE_MODEL_ID: 1700,
    TTS_CUSTOM_MODEL_ID: 1700,
}

# Preset speakers exposed by CustomVoice (Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice).
# Source: https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice — model card v1.0
# Keep this list in sync with model.generate_custom_voice's accepted speakers; if Qwen
# adds a new preset, update here AND verify TTSPresetVoicePicker.vue still renders it.
PRESET_SPEAKERS: list[str] = [
    "Vivian", "Serena", "Uncle_Fu", "Dylan", "Eric",
    "Ryan", "Aiden", "Ono_Anna", "Sohee",
]

SUPPORTED_LANGUAGES: list[str] = [
    "auto", "Chinese", "English", "Japanese", "Korean",
    "German", "French", "Russian", "Portuguese", "Spanish", "Italian",
]

# Short-code aliases — frontend may submit "zh" while qwen_tts expects "Chinese".
# Frontend dropdown fallback also uses the long names; this is a defense-in-depth
# in case a UI elsewhere passes ISO codes.
LANGUAGE_ALIASES: dict[str, str] = {
    "zh": "Chinese", "zh-CN": "Chinese", "zh-cn": "Chinese", "cn": "Chinese",
    "en": "English", "en-US": "English", "en-us": "English",
    "ja": "Japanese", "jp": "Japanese", "ja-JP": "Japanese",
    "ko": "Korean", "kr": "Korean",
    "de": "German",
    "fr": "French",
    "ru": "Russian",
    "pt": "Portuguese",
    "es": "Spanish",
    "it": "Italian",
}


def _normalize_language(value: str | None) -> str:
    """Map short codes to qwen_tts' expected long names; pass through unknowns."""
    if not value:
        return "auto"
    return LANGUAGE_ALIASES.get(value, value)

SUPPORTED_EMOTIONS: list[str] = [
    "neutral", "happy", "sad", "angry", "fearful", "disgusted", "surprised",
]

EMOTION_INSTRUCT_MAP: dict[str, str] = {
    "happy":     "in a happy tone",
    "sad":       "in a sad tone",
    "angry":     "in an angry tone",
    "fearful":   "in a fearful tone",
    "disgusted": "in a disgusted tone",
    "surprised": "in a surprised tone",
}

# ---- Internal state -----------------------------------------------------
# key = (model_id, device, dtype_str)
_tts_model_cache: dict[tuple, Any] = {}
_tts_loading_events: dict[tuple, threading.Event] = {}
_tts_last_used: dict[tuple, float] = {}
_tts_cache_lock = threading.Lock()

# 记录加载线程内抛出的异常，配合 _tts_load_lock 防止"failed once, blocked forever"。
# event.set() 之后等待方会从这里取出错误、清掉状态、抛出给调用方；
# 下次再调用 get_or_load_tts(key) 时由于 events 字典已无 key，会重新启动加载线程。
_tts_load_errors: dict[tuple, Exception] = {}
_tts_load_lock = threading.Lock()

# Public state for /api/tts/status
_tts_state: dict[str, Any] = {
    "phase": "idle",       # idle | loading | ready | error
    "percent": 0,
    "detail": "",
    "message": "",
    "error": None,
    "started_at": None,
}
_tts_state_lock = threading.Lock()

_watchdog_started = False
_watchdog_lock = threading.Lock()


def _set_state(**kwargs: Any) -> None:
    with _tts_state_lock:
        _tts_state.update(kwargs)


def _ensure_hf_cache_env(settings: Settings) -> None:
    """Point HuggingFace cache at data/qwen3_models/ before any HF call."""
    cache_dir = settings.data_dir / "qwen3_models"
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HOME", str(cache_dir))
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(cache_dir / "hub"))
    os.environ.setdefault("MODELSCOPE_CACHE", str(cache_dir / "modelscope"))


def _detect_device_dtype() -> tuple[str, str]:
    """Return (device, dtype_str). Prefer CUDA fp16; else CPU fp32."""
    try:
        import torch  # type: ignore
        if torch.cuda.is_available():
            return "cuda", "float16"
    except Exception:
        pass
    return "cpu", "float32"


# ---- Global default device/dtype (lazy, single-init) -------------------
# 解决并发线程因为 torch.cuda 探测瞬时差异产生 cuda / cpu 两份缓存的问题。
# 模块导入时 torch 可能尚未完全就绪 → 用延迟单次初始化（首次需要时锁内写入）。
_TTS_DEFAULT_DEVICE: str | None = None
_TTS_DEFAULT_DTYPE: str | None = None
_TTS_GLOBAL_DETECT_LOCK = threading.Lock()


def _ensure_default_device_dtype() -> tuple[str, str]:
    """全进程只探测一次 device/dtype，避免并发 races 产生多份缓存。"""
    global _TTS_DEFAULT_DEVICE, _TTS_DEFAULT_DTYPE
    if _TTS_DEFAULT_DEVICE is not None and _TTS_DEFAULT_DTYPE is not None:
        return _TTS_DEFAULT_DEVICE, _TTS_DEFAULT_DTYPE
    with _TTS_GLOBAL_DETECT_LOCK:
        if _TTS_DEFAULT_DEVICE is None or _TTS_DEFAULT_DTYPE is None:
            d, dt = _detect_device_dtype()
            _TTS_DEFAULT_DEVICE, _TTS_DEFAULT_DTYPE = d, dt
            logger.info(f"[TTS] global default device/dtype initialized: {d}/{dt}")
    return _TTS_DEFAULT_DEVICE, _TTS_DEFAULT_DTYPE  # type: ignore[return-value]


def _load_qwen_tts_model(model_id: str, device: str, dtype_str: str) -> Any:
    """Synchronous loader. Caller must already hold the loading event."""
    import torch  # type: ignore
    from qwen_tts import Qwen3TTSModel  # type: ignore

    dtype = torch.float16 if dtype_str == "float16" else torch.float32
    logger.info(f"[TTS] Loading {model_id} (device={device}, dtype={dtype_str}) ...")
    model = Qwen3TTSModel.from_pretrained(
        model_id,
        device_map=device,
        dtype=dtype,
        attn_implementation="eager",
    )
    logger.info(f"[TTS] Loaded {model_id}")
    return model


def get_or_load_tts(
    model_id: str,
    settings: Settings,
    *,
    device: str | None = None,
    dtype_str: str | None = None,
) -> Any:
    """Concurrent-safe lazy loader. Returns Qwen3TTSModel instance.

    若调用方显式传 device/dtype 则用显式值；否则使用全局单次初始化的默认值
    （`_ensure_default_device_dtype()`），避免不同线程探测出不同结果各自落一份缓存。
    """
    _ensure_hf_cache_env(settings)
    install_progress_hook(_tts_state)
    _ensure_watchdog(settings)

    # 使用全局默认（仅当调用方未显式指定时）
    default_device, default_dtype = _ensure_default_device_dtype()
    use_device = device or default_device
    use_dtype = dtype_str or default_dtype
    key = (model_id, use_device, use_dtype)

    with _tts_cache_lock:
        if key in _tts_model_cache:
            _tts_last_used[key] = time.time()
            return _tts_model_cache[key]
        if key in _tts_loading_events:
            event = _tts_loading_events[key]
            should_load = False
        else:
            event = threading.Event()
            _tts_loading_events[key] = event
            should_load = True

    if not should_load:
        # 等待另一个线程的加载结果；超时或失败都要给出可重试的友好错误
        event.wait(timeout=900)
        with _tts_cache_lock:
            if key in _tts_model_cache:
                return _tts_model_cache[key]
        # 检查加载线程是否记录了异常
        with _tts_load_lock:
            exc = _tts_load_errors.pop(key, None)
        # 清掉 events 里的占位 → 下次再调用本函数会重新启动加载线程
        with _tts_cache_lock:
            _tts_loading_events.pop(key, None)
        if exc is not None:
            raise RuntimeError(f"TTS 模型加载失败: {exc!s}") from exc
        raise RuntimeError(
            f"TTS 模型 {model_id} 加载未完成（超时或被其他线程异常中断），请重试"
        )

    # 本线程负责实际加载
    try:
        _set_state(
            phase="loading",
            percent=0,
            detail="",
            message=f"Loading {model_id}",
            error=None,
            started_at=time.time(),
        )
        model = _load_qwen_tts_model(model_id, use_device, use_dtype)
        with _tts_cache_lock:
            _tts_model_cache[key] = model
            _tts_last_used[key] = time.time()
        _set_state(phase="ready", percent=100, message="Model ready", detail="")
        return model
    except Exception as exc:
        # 记录到共享错误字典 → 等待方与本线程都能拿到失败原因
        with _tts_load_lock:
            _tts_load_errors[key] = exc
        _set_state(phase="error", message=f"Load failed: {exc}", error=str(exc))
        # 清理 events，让下次调用可以重新触发加载
        with _tts_cache_lock:
            _tts_loading_events.pop(key, None)
        # 本线程也清理一下自己留下的错误项（已抛给调用方，无需再保留）
        with _tts_load_lock:
            _tts_load_errors.pop(key, None)
        raise RuntimeError(f"TTS 模型加载失败: {exc!s}") from exc
    else:
        # 成功路径：清理 events，让后续调用走 cache hit 分支
        with _tts_cache_lock:
            _tts_loading_events.pop(key, None)
    finally:
        # event.set() 必须放在 finally：等待方依赖此信号
        event.set()


def unload_all() -> int:
    """Drop every cached model. Returns number unloaded."""
    with _tts_cache_lock:
        n = len(_tts_model_cache)
        _tts_model_cache.clear()
        _tts_last_used.clear()
    if n > 0:
        gc.collect()
        try:
            import torch  # type: ignore
            torch.cuda.empty_cache()
        except Exception:
            pass
        logger.info(f"[TTS] Unloaded {n} model(s)")
        _set_state(phase="idle", percent=0, message="", detail="", error=None)
    return n


def is_loading_in_progress(model_id: str, settings: Settings | None = None) -> bool:
    """True if any thread is currently inside `_load_qwen_tts_model` for this model_id.

    Used by the API layer to short-circuit /api/tts/synthesize with a 503 instead
    of blocking an ASGI worker thread for up to 900 s on `event.wait`.
    """
    device, dtype_str = _ensure_default_device_dtype()
    key = (model_id, device, dtype_str)
    with _tts_cache_lock:
        # Already in cache → not "loading" from the caller's perspective.
        if key in _tts_model_cache:
            return False
        return key in _tts_loading_events


def get_status() -> dict[str, Any]:
    """Snapshot for /api/tts/status."""
    with _tts_state_lock:
        snapshot = dict(_tts_state)
    with _tts_cache_lock:
        loaded_models = [k[0] for k in _tts_model_cache.keys()]
    snapshot["loaded_models"] = loaded_models
    snapshot["base_loaded"] = TTS_BASE_MODEL_ID in loaded_models
    snapshot["custom_loaded"] = TTS_CUSTOM_MODEL_ID in loaded_models
    snapshot["ready"] = snapshot.get("phase") == "ready" or len(loaded_models) > 0
    if snapshot.get("started_at"):
        snapshot["elapsed_sec"] = int(time.time() - snapshot["started_at"])
    else:
        snapshot["elapsed_sec"] = 0
    return snapshot


# ---- Idle-unload watchdog ----------------------------------------------
def _idle_unload_watchdog(settings: Settings) -> None:
    while True:
        time.sleep(60)
        try:
            idle_min = int(getattr(settings, "tts_idle_unload_minutes", 15))
            if idle_min <= 0:
                continue
            cutoff = time.time() - idle_min * 60
            unloaded = []
            with _tts_cache_lock:
                keys_to_unload = [k for k, t in _tts_last_used.items() if t < cutoff]
                for key in keys_to_unload:
                    _tts_model_cache.pop(key, None)
                    _tts_last_used.pop(key, None)
                    unloaded.append(key)
            if unloaded:
                gc.collect()
                try:
                    import torch  # type: ignore
                    torch.cuda.empty_cache()
                except Exception:
                    pass
                for k in unloaded:
                    logger.info(f"[TTS] idle-unloaded {k}")
                with _tts_cache_lock:
                    if not _tts_model_cache:
                        _set_state(phase="idle", percent=0, message="", detail="")
        except Exception:
            logger.exception("[TTS] watchdog iteration failed")


def _ensure_watchdog(settings: Settings) -> None:
    global _watchdog_started
    with _watchdog_lock:
        if _watchdog_started:
            return
        thread = threading.Thread(
            target=_idle_unload_watchdog,
            args=(settings,),
            daemon=True,
            name="tts-idle-watchdog",
        )
        thread.start()
        _watchdog_started = True


def start_idle_watchdog(settings: Settings) -> None:
    """Public entry — call from FastAPI startup hook."""
    _ensure_watchdog(settings)


# ---- Model management for Settings UI ----------------------------------
TTS_MODEL_KEYS: dict[str, str] = {
    "base":   TTS_BASE_MODEL_ID,
    "custom": TTS_CUSTOM_MODEL_ID,
}

TTS_MODEL_LABELS: dict[str, str] = {
    TTS_BASE_MODEL_ID:   "Base",
    TTS_CUSTOM_MODEL_ID: "CustomVoice",
}

TTS_MODEL_DESCRIPTIONS: dict[str, str] = {
    TTS_BASE_MODEL_ID:   "通用语音克隆模型；接受参考音频生成对应音色",
    TTS_CUSTOM_MODEL_ID: "9 个预设说话人（Vivian / Serena / Uncle_Fu / Dylan / Eric / Ryan / Aiden / Ono_Anna / Sohee）",
}


def _hf_cache_dir_name(model_id: str) -> str:
    """HuggingFace 本地缓存的目录命名规则：models--<owner>--<repo>"""
    return "models--" + model_id.replace("/", "--")


def _get_model_cache_dir(settings: Settings, model_id: str) -> Path:
    """data/qwen3_models/hub/models--<...>/  根目录"""
    return settings.tts_model_cache_dir / "hub" / _hf_cache_dir_name(model_id)


def _dir_size_bytes(p: Path) -> int:
    """递归累加目录字节数；忽略文件读权限错误。"""
    if not p.exists():
        return 0
    total = 0
    try:
        for root, _dirs, files in os.walk(p):
            for f in files:
                try:
                    total += (Path(root) / f).stat().st_size
                except Exception:
                    pass
    except Exception:
        pass
    return total


def _is_model_cached(model_dir: Path) -> bool:
    """目录下任意 snapshot 含 .safetensors / .bin / .pt 即视为已缓存"""
    if not model_dir.exists():
        return False
    snap_base = model_dir / "snapshots"
    if not snap_base.exists():
        return False
    for snap in snap_base.iterdir():
        if not snap.is_dir():
            continue
        for ext in (".safetensors", ".bin", ".pt"):
            if any(snap.rglob(f"*{ext}")):
                return True
    return False


def _is_model_loaded(model_id: str) -> bool:
    """检查 model_id 是否在内存缓存里（任意 device/dtype 组合）"""
    with _tts_cache_lock:
        for key in _tts_model_cache.keys():
            if key[0] == model_id:
                return True
    return False


def list_models_info(settings: Settings) -> dict[str, Any]:
    """返回 [base, custom] 两个模型的当前状态，供 Settings 页展示。"""
    _ensure_hf_cache_env(settings)
    out: list[dict[str, Any]] = []
    for key, model_id in TTS_MODEL_KEYS.items():
        cache_dir = _get_model_cache_dir(settings, model_id)
        cached = _is_model_cached(cache_dir)
        size_bytes = _dir_size_bytes(cache_dir) if cached else 0
        out.append({
            "key": key,
            "model_id": model_id,
            "label": TTS_MODEL_LABELS.get(model_id, model_id),
            "description": TTS_MODEL_DESCRIPTIONS.get(model_id, ""),
            "cached": cached,
            "cache_size_bytes": size_bytes,
            "cache_path": str(cache_dir),
            "loaded": _is_model_loaded(model_id),
            "download_size_mb": TTS_MODEL_SIZES_MB.get(model_id, 1700),
            "enabled": (
                True if key == "base"
                else bool(getattr(settings, "tts_custom_voice_enabled", False))
            ),
        })
    return {
        "models": out,
        "cache_root": str(settings.tts_model_cache_dir / "hub"),
    }


def delete_model_cache(settings: Settings, key: str) -> dict[str, Any]:
    """从磁盘删除指定模型的 HF 缓存（先 unload 内存中的实例）。

    Args:
        key: "base" | "custom"
    """
    if key not in TTS_MODEL_KEYS:
        raise ValueError(f"Unknown model key: {key}")
    model_id = TTS_MODEL_KEYS[key]
    cache_dir = _get_model_cache_dir(settings, model_id)
    cache_path = str(cache_dir)

    # 先把这个 model_id 的内存实例 unload，避免 Windows 文件占用导致 rmtree 失败
    with _tts_cache_lock:
        keys_to_drop = [k for k in _tts_model_cache.keys() if k[0] == model_id]
        for k in keys_to_drop:
            _tts_model_cache.pop(k, None)
            _tts_last_used.pop(k, None)
    if keys_to_drop:
        gc.collect()
        try:
            import torch  # type: ignore
            torch.cuda.empty_cache()
        except Exception:
            pass

    if not cache_dir.exists():
        return {
            "key": key,
            "model_id": model_id,
            "deleted": False,
            "freed_bytes": 0,
            "cache_path": cache_path,
            "message": "缓存目录不存在",
        }

    freed = _dir_size_bytes(cache_dir)
    try:
        shutil.rmtree(cache_dir, ignore_errors=False)
    except Exception as exc:
        # 二次尝试：宽容模式（部分文件被 OS 锁定时可能失败）
        shutil.rmtree(cache_dir, ignore_errors=True)
        if cache_dir.exists():
            return {
                "key": key,
                "model_id": model_id,
                "deleted": False,
                "freed_bytes": 0,
                "cache_path": cache_path,
                "message": f"删除失败：{exc}",
            }
    logger.info(f"[TTS] deleted disk cache for {model_id} ({freed} bytes)")

    # 缓存为空时把状态字典也复位
    with _tts_cache_lock:
        if not _tts_model_cache:
            _set_state(phase="idle", percent=0, message="", detail="", error=None)

    return {
        "key": key,
        "model_id": model_id,
        "deleted": True,
        "freed_bytes": freed,
        "cache_path": cache_path,
        "message": "已删除",
    }


# ---- Synthesis ----------------------------------------------------------
def _synth_default_reference_wav(out_path: Path, duration: float = 3.0, sr: int = 24000) -> None:
    """Generate a 440 Hz sine-wave WAV as a fallback reference (Base model needs ref_audio)."""
    import numpy as np
    import soundfile as sf
    t = np.linspace(0, duration, int(sr * duration), dtype=np.float32)
    audio = (0.1 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_path), audio, sr)


def _post_speed(audio: Any, speed: float) -> Any:
    """Apply speed change. Prefers librosa.effects.time_stretch (preserves pitch);
    falls back to nearest-neighbor resampling (changes pitch — chipmunk effect)
    if librosa is unavailable. Qwen3-TTS has no native speed param so this is
    always a post-process.
    """
    if speed == 1.0:
        return audio
    import numpy as np
    arr = np.asarray(audio, dtype=np.float32)
    if len(arr) <= 1:
        return arr
    try:
        import librosa  # type: ignore
        # rate>1 加快, rate<1 减慢 — 与 frontend 的 speed slider 同义
        return librosa.effects.time_stretch(y=arr, rate=float(speed)).astype(np.float32)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            f"[TTS] librosa.time_stretch unavailable ({exc!r}); "
            f"falling back to nearest-neighbor resample (will shift pitch)"
        )
        target_len = max(1, int(len(arr) / speed))
        indices = np.linspace(0, len(arr) - 1, target_len).astype(np.int64)
        return arr[indices]


def synthesize(
    settings: Settings,
    *,
    text: str,
    language: str = "auto",
    ref_audio: str | None = None,
    emotion: str | None = "neutral",
    speed: float = 1.0,
    voice: str | None = None,
    instruct: str | None = None,
) -> tuple[str, float]:
    """Run TTS. Returns (output_wav_path, duration_seconds).

    Routing:
      - voice in PRESET_SPEAKERS  → use CustomVoice.generate_custom_voice
      - else if ref_audio given   → use Base.generate_voice_clone
      - else                      → use Base.generate_voice_clone with synthetic 440Hz ref
    """
    if not text or not text.strip():
        raise ValueError("text is required")

    output_dir = settings.data_dir / "outputs" / "tts"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"tts_{uuid.uuid4().hex[:12]}.wav"

    use_custom = bool(voice and voice in PRESET_SPEAKERS)

    # Build instruct from emotion if not explicitly provided
    final_instruct = (instruct or "").strip() or EMOTION_INSTRUCT_MAP.get(
        (emotion or "neutral").lower()
    )

    normalized_lang = _normalize_language(language)

    if use_custom:
        if not getattr(settings, "tts_custom_voice_enabled", False):
            raise RuntimeError(
                "CustomVoice is disabled in settings. Enable 'tts_custom_voice_enabled' first."
            )
        model = get_or_load_tts(TTS_CUSTOM_MODEL_ID, settings)
        wavs, sr = model.generate_custom_voice(
            text=text,
            language=normalized_lang,
            speaker=voice,
            instruct=final_instruct,
        )
    else:
        model = get_or_load_tts(TTS_BASE_MODEL_ID, settings)
        # Need a reference audio. Use user-supplied or synth a fallback.
        temp_ref: Path | None = None
        if ref_audio and Path(ref_audio).exists():
            ref_to_use = ref_audio
        else:
            temp_ref = output_dir / f"_temp_ref_{uuid.uuid4().hex[:8]}.wav"
            _synth_default_reference_wav(temp_ref)
            ref_to_use = str(temp_ref)
        try:
            wavs, sr = model.generate_voice_clone(
                text=text,
                language=normalized_lang,
                ref_audio=ref_to_use,
                x_vector_only_mode=True,
                instruct=final_instruct,
            )
        finally:
            if temp_ref and temp_ref.exists():
                try:
                    temp_ref.unlink()
                except Exception:
                    pass

    audio = wavs[0]
    if hasattr(audio, "cpu"):
        audio = audio.cpu().numpy()
    audio = _post_speed(audio, float(speed))

    import soundfile as sf
    sf.write(str(output_path), audio, sr)

    duration_sec = float(len(audio)) / float(sr) if sr else 0.0
    return normalize_storage_path(output_path), duration_sec
