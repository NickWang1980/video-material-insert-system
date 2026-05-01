from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class SettingsRow(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    output_format: Mapped[str] = mapped_column(String(10), default="MP4")
    resolution: Mapped[str] = mapped_column(String(10), default="1080P")  # 720P|1080P|4K
    video_bitrate_kbps: Mapped[int] = mapped_column(Integer, default=6000)
    subtitle_encoding: Mapped[str] = mapped_column(String(30), default="utf-8")
    subtitle_time_offset_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    asr_model: Mapped[str] = mapped_column(String(20), default="small")
    asr_compute_type: Mapped[str] = mapped_column(String(20), default="auto")
    video_encoder_mode: Mapped[str] = mapped_column(String(20), default="auto")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
