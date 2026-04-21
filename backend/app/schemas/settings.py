from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class SettingsResponse(BaseModel):
    output_format: str
    resolution: str
    video_bitrate_kbps: int
    subtitle_encoding: str
    subtitle_time_offset_seconds: float
    asr_model: Literal["small", "medium"]


class SettingsUpdateRequest(SettingsResponse):
    pass
