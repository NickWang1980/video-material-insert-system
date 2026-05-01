from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class SettingsResponse(BaseModel):
    output_format: str
    resolution: str
    video_bitrate_kbps: int
    subtitle_encoding: str
    subtitle_time_offset_seconds: float
    asr_model: Literal["small", "medium", "large-v3", "large-v3-turbo"]
    asr_compute_type: Literal["auto", "int8", "float16", "float32"] = "auto"
    video_encoder_mode: Literal["auto", "cpu", "cuda", "qsv", "amf"] = "auto"


class SettingsUpdateRequest(SettingsResponse):
    pass


class AsrModelCheckRequest(BaseModel):
    model: str


class AsrModelCheckResponse(BaseModel):
    model: str
    installed: bool
    size_mb: int
    reason: str | None = None  # 不完整时给出原因，前端可展示


class AsrInstallStartResponse(BaseModel):
    task_id: str


class AsrInstallProgressResponse(BaseModel):
    model: str
    status: Literal["queued", "downloading", "completed", "failed", "cancelled"]
    progress: int
    message: str
    total_mb: int
    cancel_requested: bool = False


class AsrInstalledModelInfo(BaseModel):
    model: str
    repo: str
    installed: bool
    reason: str | None = None
    size_hint_mb: int = 0
    local_path: str
    local_exists: bool
    local_size_bytes: int = 0
    hf_cache_path: str | None = None
    hf_cache_exists: bool = False
    hf_cache_size_bytes: int = 0


class AsrModelDeleteRequest(BaseModel):
    model: str
    include_hf_cache: bool = False


class AsrModelDeleteResponse(BaseModel):
    model: str
    local_deleted: bool
    local_path: str
    hf_cache_deleted: bool = False
    hf_cache_path: str | None = None


class AsrInstallCancelResponse(BaseModel):
    ok: bool
    message: str


class FfmpegBinaryInfo(BaseModel):
    configured_path: str
    resolved_path: str | None = None
    exists: bool
    size_bytes: int = 0
    version: str = ""
    first_line: str = ""
    ok: bool = False
    error: str | None = None


class FfmpegInfoResponse(BaseModel):
    ffmpeg: FfmpegBinaryInfo
    ffprobe: FfmpegBinaryInfo
    ffmpeg_configuration: str = ""
    hw_encoders: list[str] = []
    encoder_active: str = ""


class CacheCategoryInfo(BaseModel):
    key: str
    label: str
    description: str
    safe: bool
    paths: list[str]
    size_bytes: int = 0
    file_count: int = 0


class CacheClearRequest(BaseModel):
    categories: list[str]


class CacheClearItemResult(BaseModel):
    freed_bytes: int = 0
    freed_files: int = 0
    paths: list[str] = []
    errors: list[str] = []
    error: str | None = None


class CacheClearResponse(BaseModel):
    summary: dict[str, CacheClearItemResult]
    total_freed_bytes: int = 0
    total_freed_files: int = 0


# ── 队列管理（ASR / FFmpeg）─────────────────────────────────────────────
class QueueItem(BaseModel):
    kind: str          # 'source_video' | 'rough_cut_asset' | 'task' | 'rough_cut'
    ref_id: int
    name: str
    status: str        # pending / running / processing / ...
    progress: int = 0
    model: str = ""
    extra: str = ""


class QueueListResponse(BaseModel):
    items: list[QueueItem] = []
    pending_count: int = 0
    running_count: int = 0
    total_count: int = 0


class QueueClearResponse(BaseModel):
    cancelled_source_count: int = 0       # 仅 ASR 用
    cancelled_rough_cut_count: int = 0    # 仅 ASR 用
    stopped_task_count: int = 0           # 仅 FFmpeg 用
    stopped_rough_cut_count: int = 0      # 仅 FFmpeg 用
    total_cancelled: int = 0
    total_stopped: int = 0
    note: str = ""
