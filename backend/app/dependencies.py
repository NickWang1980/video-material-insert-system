from __future__ import annotations

from collections.abc import Generator

from .config import Settings, get_settings
from .models.database import SessionLocal


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_app_settings() -> Settings:
    return get_settings()
