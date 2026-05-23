"""SQLAlchemy ORM model for the Video Gen (视频生成) module.

Phase-1 backs the heygem digital-human sidecar:
  audio (upload/tts/material) + reference video (upload/source/material)
  → POST heygem /synthesize → poll → /result → data/video_gen/{id}.mp4

`heygem_work_id` is the opaque id returned by the heygem REST sidecar; we keep
it so a frontend refresh can re-attach to an in-flight job without re-submitting.

JSON-free schema (flat columns) — Phase-2 may add a `meta_json` column if more
fields (face count, batch_size, etc.) are needed.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class VideoGenTask(Base):
    __tablename__ = "video_gen_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Display name (optional, user-supplied). Falls back to "video_gen_<id>" if empty.
    task_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # ── Audio source ────────────────────────────────────────────────────────
    # audio_source_type ∈ {upload, tts, material}
    audio_source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # Free-form reference: for `tts` → the TTS history id / audio_url;
    # for `material` → materials.id; for `upload` → empty.
    audio_source_ref: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # Resolved absolute filesystem path to the wav/mp3 sent to heygem.
    audio_path: Mapped[str] = mapped_column(String(512), nullable=False)

    # ── Reference video source ──────────────────────────────────────────────
    # video_source_type ∈ {upload, source, material}
    video_source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    video_source_ref: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    video_path: Mapped[str] = mapped_column(String(512), nullable=False)

    # ── heygem handoff ──────────────────────────────────────────────────────
    heygem_work_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    # ── Lifecycle ───────────────────────────────────────────────────────────
    # status ∈ {pending, running, succeeded, failed, cancelled, interrupted}
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    # phase: free-form short label echoed from heygem (e.g. "face_detect")
    phase: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    result_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
