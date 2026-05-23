"""Pydantic request/response schemas for the Video Gen module."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


AudioSourceType = Literal["upload", "tts", "material"]
VideoSourceType = Literal["upload", "source", "material"]
TaskStatus = Literal["pending", "running", "succeeded", "failed", "cancelled", "interrupted"]


class VideoGenCreateRequest(BaseModel):
    """JSON body for POST /api/video-gen.

    Files (when `audio_source_type=upload` or `video_source_type=upload`)
    are uploaded via separate multipart fields on the same request; the
    backend resolves them and writes to data/uploads/video_gen/ before
    POSTing to heygem.
    """
    task_name: Optional[str] = Field(default=None, max_length=255)
    audio_source_type: AudioSourceType
    audio_source_ref: Optional[str] = Field(default=None, max_length=500)
    video_source_type: VideoSourceType
    video_source_ref: Optional[str] = Field(default=None, max_length=500)


class VideoGenTaskResponse(BaseModel):
    id: int
    task_name: Optional[str]
    audio_source_type: AudioSourceType
    audio_source_ref: Optional[str]
    audio_path: str
    video_source_type: VideoSourceType
    video_source_ref: Optional[str]
    video_path: str
    heygem_work_id: Optional[str]
    status: TaskStatus
    phase: Optional[str]
    progress: int
    result_path: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class VideoGenListResponse(BaseModel):
    items: list[VideoGenTaskResponse]
    total: int
    limit: int
    offset: int


class VideoGenHealthResponse(BaseModel):
    enabled: bool
    reachable: bool
    base_url: str
    detail: Optional[str] = None
    heygem_ready: Optional[bool] = None
    heygem_gpu: Optional[str] = None
    heygem_version: Optional[str] = None


class VideoGenSaveToMaterialRequest(BaseModel):
    """Optional metadata when promoting a generated video to the material library."""
    library_kind: Literal["unfiled", "general", "product"] = "unfiled"
    product_id: Optional[int] = None
    script_folder_id: Optional[int] = None
    display_name: Optional[str] = Field(default=None, max_length=255)


class VideoGenSaveToMaterialResponse(BaseModel):
    material_id: int
    message: str
