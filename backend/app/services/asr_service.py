from __future__ import annotations

import glob
import json
import os
import re
import sys
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

ASR_MODEL_REPOS_PYTORCH: dict[str, str] = {
    "small":          "openai/whisper-small",
    "medium":         "openai/whisper-medium",
    "large-v3":       "openai/whisper-large-v3",
    "large-v3-turbo": "openai/whisper-large-v3",
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
_cuda_dll_ok_cache: bool | None = None


def _detect_cuda_available() -> bool:
    global _cuda_available_cache
    if _cuda_available_cache is not None:
        return _cuda_available_cache
    try:
        import ctranslate2  # type: ignore
        device_count = ctranslate2.get_cuda_device_count()
        _cuda_available_cache = device_count > 0
        logger.info(f"ASR CUDA device count: {device_count}, available: {_cuda_available_cache}")
    except Exception as e:
        logger.warning(f"Failed to detect CUDA: {e}")
        _cuda_available_cache = False
    return _cuda_available_cache


def _detect_cuda_available_pytorch() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except Exception:
        return False


def _get_pytorch_device() -> str:
    if _detect_cuda_available_pytorch():
        return "cuda"
    return "cpu"


def _check_cuda_dlls() -> bool:
    """Check if CUDA DLLs are actually loadable.

    Also adds CUDA bin directories to DLL search path.
    """
    global _cuda_dll_ok_cache
    if _cuda_dll_ok_cache is not None:
        return _cuda_dll_ok_cache
    try:
        import ctypes
        if sys.platform == "win32":
            # CTranslate2 4.x + torch CUDA 必需运行时 DLL 的"模式"列表。
            # CUDA 12.x 不同 patch 释出过不同副号（cudart64_12.dll / cudart64_120.dll /
            # cudart64_125.dll 等），cuDNN 也有 cudnn64_8 / cudnn64_9 等版本——
            # 用 glob 通配匹配代替硬编码。任一匹配视为"检测到"。
            dll_patterns = [
                "cudart64_12*.dll",
                "cublas64_12*.dll",
                "cublasLt64_12*.dll",
                "cudnn64_*.dll",
            ]
            search_dirs = []

            project_cuda_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "tools", "cuda", "bin")
            if os.path.isdir(project_cuda_dir):
                search_dirs.append(project_cuda_dir)

            cuda_path = os.environ.get("CUDA_PATH")
            if cuda_path:
                cuda_bin_dir = os.path.join(cuda_path, "bin", "x64")
                if os.path.isdir(cuda_bin_dir):
                    search_dirs.append(cuda_bin_dir)
                cuda_bin_dir = os.path.join(cuda_path, "bin")
                if os.path.isdir(cuda_bin_dir):
                    search_dirs.append(cuda_bin_dir)

            default_cuda_paths = [
                r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin\x64",
                r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin",
                r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4\bin\x64",
                r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4\bin",
                r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.2\bin\x64",
                r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.2\bin",
                r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.2\bin\x64",
                r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.2\bin",
                r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.1\bin\x64",
                r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.1\bin",
                r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.0\bin\x64",
                r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.0\bin",
            ]
            for d in default_cuda_paths:
                if os.path.isdir(d):
                    search_dirs.append(d)

            # 把 PATH 中的目录也加入搜索（pip install nvidia-cublas-cu12 等场景）
            path_env = os.environ.get("PATH", "")
            for d in path_env.split(os.pathsep):
                d = d.strip().strip('"')
                if d and os.path.isdir(d) and d not in search_dirs:
                    search_dirs.append(d)

            for d in search_dirs:
                try:
                    os.add_dll_directory(d)
                    logger.debug(f"Added DLL directory: {d}")
                except Exception as e:
                    logger.debug(f"Skip add_dll_directory {d}: {e}")

            # —— 通配匹配 + ctypes 加载尝试 ——
            found_any = False
            for pattern in dll_patterns:
                matched_files: list[str] = []
                for d in search_dirs:
                    try:
                        matched_files.extend(glob.glob(os.path.join(d, pattern)))
                    except Exception:
                        continue
                if not matched_files:
                    # 再尝试在默认 DLL 搜索路径下用名字（无目录）glob —— 多数情况下空，
                    # 保留兜底：直接交给 ctypes 用 pattern 的"代表名"试加载。
                    continue
                # 找到了文件，仍尝试用 ctypes.WinDLL 加载至少一个，确认真的可用
                for file_path in matched_files:
                    try:
                        ctypes.WinDLL(file_path)
                        logger.debug(f"CUDA DLL loadable: {file_path}")
                        found_any = True
                        break
                    except OSError as exc:
                        logger.debug(f"CUDA DLL match but load failed: {file_path} ({exc})")
                        continue

            # 兜底：若通配在已知 search_dirs 里未匹配到，再用上方同一份
            # dll_patterns 的"代表名"交给 OS 默认 DLL 搜索机制（覆盖
            # cuDNN 装在系统目录 / 其它非 PATH 路径的场景）。这里不再硬
            # 编码 cudart64_120 / cudnn64_8 等具体副号——和上方 glob 保持
            # 同一份模式列表，避免新副号漏检。
            if not found_any:
                # 同一目录里若装了多个副号，cuDNN 9 优先于 8；cudart/cublas
                # 用 pattern 名（CDLL 接受不带具体副号的"base"在部分 wheel
                # 包装里同样可加载，否则会 OSError 进入下一轮）。
                legacy_candidates: list[str] = []
                for pattern in dll_patterns:
                    if pattern == "cudnn64_*.dll":
                        legacy_candidates.extend(["cudnn64_9.dll", "cudnn64_8.dll"])
                    else:
                        # 例如 "cudart64_12*.dll" → 试 "cudart64_12.dll"
                        legacy_candidates.append(pattern.replace("*", ""))
                for legacy_name in legacy_candidates:
                    try:
                        ctypes.CDLL(legacy_name)
                        logger.debug(f"CUDA DLL loadable (legacy): {legacy_name}")
                        found_any = True
                        break
                    except OSError:
                        continue

            if not found_any:
                _cuda_dll_ok_cache = False
                logger.warning(
                    "未检测到可用 CUDA 运行时 DLL（已尝试 cudart64_12*/cublas64_12*"
                    "/cublasLt64_12*/cudnn64_*）。解决方向："
                    "(1) 在设置中将 ASR 精度改为 int8 绕过 CUDA；"
                    "(2) `pip install nvidia-cublas-cu12 nvidia-cudnn-cu12` 拉取 wheel；"
                    "(3) 安装完整 CUDA Toolkit 12.x + cuDNN。"
                )
                return False
        _cuda_dll_ok_cache = True
        logger.info("CUDA DLL check passed")
        return True
    except Exception as e:
        logger.warning(f"CUDA DLL check failed: {e}")
        _cuda_dll_ok_cache = False
        return False


def _resolve_device_compute(compute_pref: str | None) -> tuple[str, str]:
    """Resolve user's compute preference to (device, compute_type) for WhisperModel.

    compute_pref: "auto" | "int8" | "float16" | "float32"
    规则：
      - int8 始终走 CPU，绝不与 CUDA 混用（int8_float16 在 CUDA 上质量与速度
        都不如纯 float16，反而失去 int8 的内存优势——属于劣解）。
      - float16 / float32 必须走 CUDA，CUDA 不可用时抛出错误（不回退 CPU）。
      - auto：有 CUDA 用 float16，无 CUDA 用 int8（CPU 上最快）。
    """
    has_cuda = _detect_cuda_available()
    pref = (compute_pref or "auto").strip().lower()
    logger.info(f"Resolving device/compute: pref={pref}, has_cuda={has_cuda}")

    # int8 显式选择 → 强制 CPU（不与 CUDA 混用）
    if pref == "int8":
        logger.info("User selected int8, using CPU")
        return "cpu", "int8"

    # float16 / float32 需要 CUDA
    if pref in ("float16", "float32"):
        if not has_cuda:
            raise RuntimeError(
                f"ASR 精度设置为 {pref}，但未检测到 CUDA 设备。"
                "请确保已安装 NVIDIA GPU 驱动，或在设置中将 ASR 精度改为 int8。"
            )
        if not _check_cuda_dlls():
            raise RuntimeError(
                f"ASR 精度设置为 {pref}，但 CUDA 运行时库 (cublas64_12.dll) 无法加载。"
                "请运行 precheck.sh 下载 CUDA 运行时库，或安装 CUDA Toolkit 12.x，"
                "或在设置中将 ASR 精度改为 int8。"
            )
        if pref == "float32":
            logger.info("Using CUDA with float32")
            return "cuda", "float32"
        logger.info("Using CUDA with float16")
        return "cuda", "float16"

    # auto 模式：有 CUDA 用 float16，无 CUDA 用 int8
    if has_cuda:
        if not _check_cuda_dlls():
            logger.warning("CUDA 设备存在但 DLL 不可用，使用 CPU + int8")
            return "cpu", "int8"
        logger.info("Auto mode: using CUDA with float16")
        return "cuda", "float16"

    # 无 CUDA，使用 CPU + int8
    logger.info("Auto mode: no CUDA, using CPU + int8")
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


def _load_faster_whisper_model(model_name_or_path: str, device: str, compute_type: str):
    from faster_whisper import WhisperModel
    logger.info(
        f"Loading FasterWhisper: model={model_name_or_path} device={device} compute_type={compute_type}"
    )
    model = WhisperModel(model_name_or_path, device=device, compute_type=compute_type)
    return model, "faster-whisper"


def _load_pytorch_whisper_model(model_name_or_path: str, model_size: str):
    import torch
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

    device = _get_pytorch_device()
    torch_dtype = torch.float16 if device == "cuda" else torch.float32

    repo_id = ASR_MODEL_REPOS_PYTORCH.get(model_size, "openai/whisper-small")

    logger.info(
        f"Loading PyTorch Whisper: repo={repo_id} device={device} dtype={torch_dtype}"
    )

    model = AutoModelForSpeechSeq2Seq.from_pretrained(
        repo_id,
        torch_dtype=torch_dtype,
        low_cpu_mem_usage=True,
    )
    model.to(device)

    processor = AutoProcessor.from_pretrained(repo_id)

    pipe = pipeline(
        "automatic-speech-recognition",
        model=model,
        tokenizer=processor.tokenizer,
        feature_extractor=processor.feature_extractor,
        max_new_tokens=256,
        torch_dtype=torch_dtype,
        device=device,
    )
    return pipe, "transformers"


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

    use_pytorch = False
    model_size = _normalize_asr_model(None)

    try:
        model_obj, backend_name = _load_faster_whisper_model(
            model_name_or_path, device, compute_type
        )
    except Exception as faster_exc:
        logger.warning(f"FasterWhisper failed ({faster_exc}), trying PyTorch backend...")
        try:
            model_obj, backend_name = _load_pytorch_whisper_model(
                model_name_or_path, model_size
            )
            use_pytorch = True
        except Exception as pytorch_exc:
            logger.error(f"PyTorch Whisper also failed: {pytorch_exc}")
            with _whisper_model_cache_lock:
                _whisper_loading_events.pop(cache_key, None)
            event.set()
            raise RuntimeError(
                f"ASR 模型加载失败：FasterWhisper ({faster_exc}) 和 PyTorch Whisper ({pytorch_exc}) 均不可用"
            ) from pytorch_exc

    wrapped = _PyTorchWhisperWrapper(model_obj, use_pytorch) if use_pytorch else model_obj

    with _whisper_model_cache_lock:
        _whisper_model_cache[cache_key] = wrapped
        _whisper_loading_events.pop(cache_key, None)
    event.set()
    return wrapped


class _PyTorchWhisperWrapper:
    def __init__(self, pipe, is_pytorch: bool):
        self.pipe = pipe
        self.is_pytorch = is_pytorch

    @staticmethod
    def _safe_float(value, default=None):
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _probe_audio_duration(audio_path: str) -> float | None:
        """尝试用 soundfile 读取总时长；失败返回 None，调用方决定占位策略。"""
        try:
            import soundfile as sf  # type: ignore
            info = sf.info(audio_path)
            if info.samplerate and info.frames:
                return float(info.frames) / float(info.samplerate)
        except Exception:
            pass
        return None

    def transcribe(self, audio_path: str, **kwargs):
        """解析 transformers ASR pipeline 返回值。

        transformers 不同版本/不同配置下 result 可能是：
          1) {"chunks": [{"text":..., "timestamp": (start, end) | [start, end]}, ...], "text":...}
          2) {"segments": [{"text":..., "start":..., "end":..., "words":[...]}, ...]}
          3) {"text": "..."}（无时间戳，老版本或 chunk_length_s 未配置）
          4) 仅字符串

        本方法对三种 dict 形式逐一 fallback，并对每条 chunk 做异常隔离。
        """
        result = self.pipe(audio_path, **kwargs)
        segments: list[_Chunk] = []

        # 兼容：某些 pipeline 直接返回 str
        if isinstance(result, str):
            text = result.strip()
            if not text:
                raise RuntimeError("Whisper 返回格式无法解析：返回为空字符串")
            dur = self._probe_audio_duration(audio_path) or 0.0
            return [_Chunk(text=text, start=0.0, end=max(dur, 0.01), words=[])], None

        if not isinstance(result, dict):
            raise RuntimeError(
                f"Whisper 返回格式无法解析：非 dict 类型 ({type(result).__name__})"
            )

        # —— 1. 优先解析 chunks ——
        chunks = result.get("chunks")
        if isinstance(chunks, list) and len(chunks) > 0:
            for idx, chunk in enumerate(chunks):
                try:
                    if not isinstance(chunk, dict):
                        logger.warning(f"[ASR] chunk #{idx} 非 dict，跳过")
                        continue
                    text = (chunk.get("text") or "").strip()
                    ts = chunk.get("timestamp")
                    # timestamp 可能是 tuple / list；两端任一为 None 时跳过
                    if not isinstance(ts, (tuple, list)) or len(ts) < 2:
                        logger.warning(f"[ASR] chunk #{idx} 缺少 timestamp，跳过")
                        continue
                    start = self._safe_float(ts[0])
                    end = self._safe_float(ts[1])
                    if start is None or end is None:
                        logger.warning(f"[ASR] chunk #{idx} timestamp 含 None，跳过")
                        continue
                    if not text:
                        # 允许空文本但有时间戳 → 跳过，避免污染 SRT
                        continue
                    segments.append(_Chunk(text=text, start=start, end=end, words=[]))
                except Exception as exc:  # noqa: BLE001
                    logger.warning(f"[ASR] 解析 chunk #{idx} 失败，跳过: {exc!r}")
                    continue
            if segments:
                return segments, None
            logger.warning("[ASR] chunks 字段存在但全部解析失败，尝试 segments fallback")

        # —— 2. fallback: segments ——
        seg_list = result.get("segments")
        if isinstance(seg_list, list) and len(seg_list) > 0:
            for idx, seg in enumerate(seg_list):
                try:
                    if not isinstance(seg, dict):
                        logger.warning(f"[ASR] segment #{idx} 非 dict，跳过")
                        continue
                    text = (seg.get("text") or "").strip()
                    start = self._safe_float(seg.get("start"))
                    end = self._safe_float(seg.get("end"))
                    if start is None or end is None:
                        logger.warning(f"[ASR] segment #{idx} 缺少 start/end，跳过")
                        continue
                    if not text:
                        continue
                    words: list[_Word] = []
                    raw_words = seg.get("words")
                    if isinstance(raw_words, list):
                        for w in raw_words:
                            if not isinstance(w, dict):
                                continue
                            try:
                                ws = self._safe_float(w.get("start"), 0.0)
                                we = self._safe_float(w.get("end"), 0.0)
                                words.append(_Word(
                                    word=w.get("word", ""),
                                    start=ws if ws is not None else 0.0,
                                    end=we if we is not None else 0.0,
                                ))
                            except Exception as wexc:  # noqa: BLE001
                                logger.warning(
                                    f"[ASR] segment #{idx} word 解析失败，跳过: {wexc!r}"
                                )
                                continue
                    segments.append(_Chunk(text=text, start=start, end=end, words=words))
                except Exception as exc:  # noqa: BLE001
                    logger.warning(f"[ASR] 解析 segment #{idx} 失败，跳过: {exc!r}")
                    continue
            if segments:
                return segments, None
            logger.warning("[ASR] segments 字段存在但全部解析失败，尝试整段 text fallback")

        # —— 3. fallback: 整段 text ——
        whole_text = (result.get("text") or "").strip()
        if whole_text:
            duration = self._probe_audio_duration(audio_path)
            # 若无法获取真实时长，给一个保守占位（避免 end<=start 触发下游报错）
            end_ts = duration if (duration is not None and duration > 0) else 60.0
            logger.warning(
                "[ASR] Whisper 未返回时间戳，使用整段 text + 占位 end=%.2fs",
                end_ts,
            )
            return [_Chunk(text=whole_text, start=0.0, end=end_ts, words=[])], None

        # —— 4. 全都缺失 ——
        raise RuntimeError(
            "Whisper 返回格式无法解析：缺少 chunks/segments/text 字段"
        )


class _Chunk:
    def __init__(self, text, start, end, words):
        self.text = text
        self.start = start
        self.end = end
        self.words = words


class _Word:
    def __init__(self, word, start, end):
        self.word = word
        self.start = start
        self.end = end


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
