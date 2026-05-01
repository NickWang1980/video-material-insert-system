from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_name: Mapped[str] = mapped_column(String(255), index=True)
    video_path: Mapped[str] = mapped_column(String(512))
    subtitle_path: Mapped[str] = mapped_column(String(512))
    source_entry_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("source_video_entries.id"), nullable=True, index=True
    )
    subtitle_source: Mapped[str] = mapped_column(String(20), default="uploaded")
    add_subtitle_to_video: Mapped[bool] = mapped_column(Boolean, default=False)
    config_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("config_templates.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|processing|completed|failed
    progress: Mapped[int] = mapped_column(Integer, default=0)
    output_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    report_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    asr_model_used: Mapped[str | None] = mapped_column(String(20), nullable=True)
    asr_compute_type_used: Mapped[str | None] = mapped_column(String(20), nullable=True)
    video_encoder_used: Mapped[str | None] = mapped_column(String(40), nullable=True)
    video_resolution_used: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
