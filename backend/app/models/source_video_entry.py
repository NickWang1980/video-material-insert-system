from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class SourceVideoEntry(Base):
    __tablename__ = "source_video_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    video_path: Mapped[str] = mapped_column(String(512))
    subtitle_path: Mapped[str] = mapped_column(String(512))
    video_width: Mapped[int] = mapped_column(Integer)
    video_height: Mapped[int] = mapped_column(Integer)
    video_aspect_ratio: Mapped[str] = mapped_column(String(20))
    video_duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    audio_wav_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    audio_flac_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    asr_srt_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    asr_status: Mapped[str] = mapped_column(String(20), default="pending")
    asr_progress: Mapped[int] = mapped_column(Integer, default=0)
    asr_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    asr_retry_count: Mapped[int] = mapped_column(Integer, default=0)
    asr_retry_max: Mapped[int] = mapped_column(Integer, default=3)
    subtitle_line_count_user: Mapped[int | None] = mapped_column(Integer, nullable=True)
    subtitle_line_count_asr: Mapped[int | None] = mapped_column(Integer, nullable=True)
    asr_model_used: Mapped[str | None] = mapped_column(String(20), nullable=True)
    asr_compute_type_used: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
