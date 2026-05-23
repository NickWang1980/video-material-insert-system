from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class TTSSynthesizeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    language: str = "auto"
    ref_audio: Optional[str] = None
    voice: Optional[str] = None  # CustomVoice preset speaker name
    emotion: Optional[str] = "neutral"
    speed: float = Field(1.0, ge=0.5, le=2.0)
    instruct: Optional[str] = None  # free-form override for emotion


class TTSSynthesizeResponse(BaseModel):
    status: str = "success"
    audio_url: str
    duration_sec: float
    message: str = "Speech generated successfully"


class TTSStatusResponse(BaseModel):
    phase: str  # idle | loading | ready | error
    percent: int
    detail: str = ""
    message: str = ""
    error: Optional[str] = None
    elapsed_sec: int = 0
    ready: bool = False
    base_loaded: bool = False
    custom_loaded: bool = False
    loaded_models: list[str] = []


class TTSVoiceInfo(BaseModel):
    code: str
    description: str = ""


class TTSReferenceUploadResponse(BaseModel):
    status: str = "success"
    ref_audio_path: str
    message: str = "Reference audio uploaded"


class TTSEnumValue(BaseModel):
    code: str
    name: str


class TTSModelInfo(BaseModel):
    """Per-model status used by Settings page TTS management section."""
    key: str                 # "base" | "custom"
    model_id: str            # full HF repo id
    label: str               # "Base" | "CustomVoice"
    description: str = ""
    cached: bool             # at least one snapshot dir on disk with .safetensors/.bin
    cache_size_bytes: int = 0
    cache_path: str = ""     # the snapshot dir or expected location
    loaded: bool             # currently held in process RAM/VRAM
    download_size_mb: int    # approximate download size
    enabled: bool = True     # for "custom": mirrors tts_custom_voice_enabled


class TTSModelListResponse(BaseModel):
    models: list[TTSModelInfo]
    cache_root: str          # data/qwen3_models/hub/


class TTSModelDeleteResponse(BaseModel):
    key: str
    model_id: str
    deleted: bool
    freed_bytes: int = 0
    cache_path: str = ""
    message: str = ""

