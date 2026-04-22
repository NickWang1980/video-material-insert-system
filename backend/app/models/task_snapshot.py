from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class TaskConfigSnapshot(Base):
    __tablename__ = "task_config_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("tasks.id"), index=True)
    config_json: Mapped[str] = mapped_column(Text)
    source_templates_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    keyword_collision_warnings_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    collision_priority_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
