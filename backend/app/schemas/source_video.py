from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SourceVideoEntryResponse(BaseModel):
    id: int
    name: str
    video_path: str
    subtitle_path: str
    video_width: int
    video_height: int
    video_aspect_ratio: str
    video_duration_seconds: float | None = None
    audio_wav_path: str | None = None
    audio_flac_path: str | None = None
    asr_srt_path: str | None = None
    asr_status: str
    asr_progress: int = 0
    asr_error: str | None = None
    asr_retry_count: int = 0
    asr_retry_max: int = 3
    subtitle_line_count_user: int | None = None
    subtitle_line_count_asr: int | None = None
    asr_model_used: str | None = None
    asr_compute_type_used: str | None = None
    has_wav: bool = False
    has_flac: bool = False
    has_uploaded_srt: bool = False
    has_asr_srt: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SourceVideoEntryRenameRequest(BaseModel):
    name: str


class ParsedSubtitleLine(BaseModel):
    index: int
    start: str
    end: str
    text: str
    start_seconds: float
    end_seconds: float
    duration: float


class ParsedSubtitleResponse(BaseModel):
    source: str
    line_count: int
    lines: list[ParsedSubtitleLine]
