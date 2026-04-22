from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    file_name: Mapped[str] = mapped_column(String(255), index=True)
    file_type: Mapped[str] = mapped_column(String(20))  # image|gif|video|audio
    file_size: Mapped[int] = mapped_column(Integer)
    file_path: Mapped[str] = mapped_column(String(512))
    library_kind: Mapped[str] = mapped_column(String(20), default="general")
    product_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    script_folder: Mapped[str | None] = mapped_column(String(255), nullable=True)
    product_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("material_products.id"), nullable=True, index=True
    )
    script_folder_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("material_script_folders.id"), nullable=True, index=True
    )
    audio_removed: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    product = relationship("MaterialProduct", back_populates="materials")
    script_folder_ref = relationship("MaterialScriptFolder", back_populates="materials")
    folder_bindings = relationship(
        "MaterialFolderBinding",
        back_populates="material",
        cascade="all, delete-orphan",
    )
