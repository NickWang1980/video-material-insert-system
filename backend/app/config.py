from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    database_url: str
    data_dir: Path
    ffmpeg_bin: str
    ffprobe_bin: str
    db_encryption_key: str
    jwt_secret: str
    # ---- TTS (Qwen3-TTS) ---------------------------------------------------
    # Model identifier loaded by tts_service. Override via TTS_MODEL_NAME env.
    tts_model_name: str = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
    # After this many minutes of no /api/tts requests, the watchdog unloads
    # cached TTS models to free ~7 GB RAM. Set to 0 to disable auto-unload.
    tts_idle_unload_minutes: int = 15
    # When True, the CustomVoice model (9 preset speakers) is loadable.
    # Default off: avoids pulling an extra 1.7 GB model + 3 GB RAM at startup.
    tts_custom_voice_enabled: bool = False
    # HuggingFace cache base. Defaults to data/qwen3_models inside data_dir.
    tts_model_cache_dir: Path = Path("")  # filled in get_settings()
    # ---- Copy Gen (文案生成) ----------------------------------------------
    # Default LLM endpoint (overridable per saved ModelConfig row in DB).
    copy_gen_default_base_url: str = "https://api.openai.com/v1"
    copy_gen_default_model: str = "gpt-4o-mini"
    # Hard timeout for a single LLM call (per version).
    copy_gen_timeout: int = 120
    # Fernet key used to encrypt api_key columns. If unset, the service will
    # auto-generate one and persist it under data/.copy_gen_key.
    copy_gen_llm_key: str = ""
    # ---- Video Gen (heygem 数字人 sidecar) --------------------------------
    # heygem REST sidecar base URL (see vendor/heygem/api_server.py).
    heygem_base_url: str = "http://127.0.0.1:8383"
    # When False, the /video-gen page shows "未连接，已禁用"。后端拒绝创建任务。
    heygem_enabled: bool = True
    # heygem 单任务硬超时（秒）。数字人推理经验值 ≈ video_duration × 1.5 + 30s。
    heygem_request_timeout: int = 600
    # 显存协调策略：
    #   "manual"       —— Phase-1 默认；不做任何自动卸载；用户自己保证不冲突
    #   "tts_unload"   —— 提交 heygem 任务前主动调 TTS unload_all() （Phase-2 实装）
    #   "cuda_isolate" —— 在 vendor/heygem/start_api.bat 注入 CUDA_VISIBLE_DEVICES=1
    #                     （Phase-2 实装，且要求物理双卡）
    video_gen_vram_strategy: str = "manual"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is not None:
        return _settings

    # Load .env from backend/ if present, else repo root.
    backend_dir = Path(__file__).resolve().parents[1]
    repo_root = backend_dir.parent
    load_dotenv(backend_dir / ".env", override=False)
    load_dotenv(repo_root / ".env", override=False)

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    database_url = os.getenv("DATABASE_URL", "sqlite:///./data/database.db")
    data_dir_env = os.getenv("DATA_DIR", str(repo_root / "data"))
    data_dir = Path(data_dir_env).resolve()
    ffmpeg_bin = os.getenv("FFMPEG_BIN", "ffmpeg")
    ffprobe_bin = os.getenv("FFPROBE_BIN", "ffprobe")
    db_encryption_key = os.getenv("DB_ENCRYPTION_KEY", "")
    jwt_secret = os.getenv("JWT_SECRET", "vmis-default-secret-change-in-prod")

    # ---- TTS settings -----------------------------------------------------
    tts_model_name = os.getenv("TTS_MODEL_NAME", "Qwen/Qwen3-TTS-12Hz-1.7B-Base")
    try:
        tts_idle_unload_minutes = int(os.getenv("TTS_IDLE_UNLOAD_MINUTES", "15"))
    except ValueError:
        tts_idle_unload_minutes = 15
    tts_custom_voice_enabled = os.getenv("TTS_CUSTOM_VOICE_ENABLED", "0").strip().lower() in {
        "1", "true", "yes", "on",
    }
    tts_cache_env = os.getenv("TTS_MODEL_CACHE_DIR", "")
    tts_model_cache_dir = (
        Path(tts_cache_env).resolve() if tts_cache_env else (data_dir / "qwen3_models")
    )

    # ---- Copy Gen settings -----------------------------------------------
    copy_gen_default_base_url = os.getenv(
        "COPY_GEN_DEFAULT_BASE_URL", "https://api.openai.com/v1"
    )
    copy_gen_default_model = os.getenv("COPY_GEN_DEFAULT_MODEL", "gpt-4o-mini")
    try:
        copy_gen_timeout = int(os.getenv("COPY_GEN_TIMEOUT", "120"))
    except ValueError:
        copy_gen_timeout = 120
    copy_gen_llm_key = os.getenv("COPY_GEN_LLM_KEY", "")

    # ---- Video Gen settings ----------------------------------------------
    heygem_base_url = os.getenv("HEYGEM_BASE_URL", "http://127.0.0.1:8383")
    heygem_enabled = os.getenv("HEYGEM_ENABLED", "1").strip().lower() in {
        "1", "true", "yes", "on",
    }
    try:
        heygem_request_timeout = int(os.getenv("HEYGEM_REQUEST_TIMEOUT", "600"))
    except ValueError:
        heygem_request_timeout = 600
    video_gen_vram_strategy = os.getenv("VIDEO_GEN_VRAM_STRATEGY", "manual").strip().lower()
    if video_gen_vram_strategy not in {"manual", "tts_unload", "cuda_isolate"}:
        video_gen_vram_strategy = "manual"

    # Normalize sqlite path to be repo-root-relative when using the default ./data path.
    if database_url.startswith("sqlite:///./"):
        rel = database_url.removeprefix("sqlite:///./")
        database_url = f"sqlite:///{(repo_root / rel).resolve().as_posix()}"

    _settings = Settings(
        host=host,
        port=port,
        database_url=database_url,
        data_dir=data_dir,
        ffmpeg_bin=ffmpeg_bin,
        ffprobe_bin=ffprobe_bin,
        db_encryption_key=db_encryption_key,
        jwt_secret=jwt_secret,
        tts_model_name=tts_model_name,
        tts_idle_unload_minutes=tts_idle_unload_minutes,
        tts_custom_voice_enabled=tts_custom_voice_enabled,
        tts_model_cache_dir=tts_model_cache_dir,
        copy_gen_default_base_url=copy_gen_default_base_url,
        copy_gen_default_model=copy_gen_default_model,
        copy_gen_timeout=copy_gen_timeout,
        copy_gen_llm_key=copy_gen_llm_key,
        heygem_base_url=heygem_base_url,
        heygem_enabled=heygem_enabled,
        heygem_request_timeout=heygem_request_timeout,
        video_gen_vram_strategy=video_gen_vram_strategy,
    )
    return _settings
