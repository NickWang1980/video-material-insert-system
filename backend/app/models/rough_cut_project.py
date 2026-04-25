from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class RoughCutProject(Base):
    __tablename__ = "rough_cut_projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), default="多角色混剪")
    script_text: Mapped[str] = mapped_column(Text, default="")
    sentences_json: Mapped[str] = mapped_column(Text, default="[]")
    roles_json: Mapped[str] = mapped_column(Text, default="[]")
    assets_json: Mapped[str] = mapped_column(Text, default="[]")
    settings_json: Mapped[str] = mapped_column(Text, default="{}")
    timeline_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(20), default="idle")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    phase: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    log_text: Mapped[str] = mapped_column(Text, default="")
    preview_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    output_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    @property
    def script_file_name(self) -> str | None:
        try:
            payload = json.loads(self.settings_json or "{}")
        except Exception:
            return None
        value = str(payload.get("scriptFileName") or "").strip()
        return value or None

    @script_file_name.setter
    def script_file_name(self, value: str | None) -> None:
        try:
            payload = json.loads(self.settings_json or "{}")
            if not isinstance(payload, dict):
                payload = {}
        except Exception:
            payload = {}
        normalized = str(value or "").strip()
        if normalized:
            payload["scriptFileName"] = normalized
        else:
            payload.pop("scriptFileName", None)
        self.settings_json = json.dumps(payload, ensure_ascii=False)
