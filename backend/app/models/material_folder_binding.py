from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class MaterialFolderBinding(Base):
    __tablename__ = "material_folder_bindings"
    __table_args__ = (
        UniqueConstraint("material_id", "script_folder_id", name="uq_material_script_binding"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    material_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("materials.id"), index=True
    )
    script_folder_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("material_script_folders.id"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    material = relationship("Material", back_populates="folder_bindings")
    script_folder = relationship("MaterialScriptFolder", back_populates="folder_bindings")
