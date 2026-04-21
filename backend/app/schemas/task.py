from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SourceTemplate(BaseModel):
    id: int
    name: str


class SourceVideoRef(BaseModel):
    id: int
    name: str


class TaskResponse(BaseModel):
    id: int
    task_name: str
    status: str
    progress: int
    created_at: datetime
    completed_at: datetime | None = None

    output_path: str | None = None
    report_path: str | None = None
    video_width: int | None = None
    video_height: int | None = None
    video_aspect_ratio: str | None = None
    source_templates: list[SourceTemplate] = Field(default_factory=list)
    source_video: SourceVideoRef | None = None
    subtitle_source: str = "uploaded"
    add_subtitle_to_video: bool = False

    model_config = ConfigDict(from_attributes=True)


class TaskListResponse(BaseModel):
    items: list[TaskResponse]
    total: int
