from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class MaterialScriptFolder(Base):
    __tablename__ = "material_script_folders"
    __table_args__ = (UniqueConstraint("product_id", "name", name="uq_script_folder_product_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("material_products.id"), index=True
    )
    name: Mapped[str] = mapped_column(String(255), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    product = relationship("MaterialProduct", back_populates="script_folders")
    materials = relationship("Material", back_populates="script_folder_ref")
    folder_bindings = relationship(
        "MaterialFolderBinding",
        back_populates="script_folder",
        cascade="all, delete-orphan",
    )
