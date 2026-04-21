from __future__ import annotations

import os
import shutil
from pathlib import Path

from ..config import Settings


def ensure_data_layout(settings: Settings) -> None:
    data_dir = settings.data_dir
    (data_dir / "uploads" / "videos").mkdir(parents=True, exist_ok=True)
    (data_dir / "uploads" / "subtitles").mkdir(parents=True, exist_ok=True)
    (data_dir / "uploads" / "subtitles" / "asr").mkdir(parents=True, exist_ok=True)
    (data_dir / "uploads" / "source_audio").mkdir(parents=True, exist_ok=True)
    (data_dir / "uploads" / "materials" / "images").mkdir(parents=True, exist_ok=True)
    (data_dir / "uploads" / "materials" / "gifs").mkdir(parents=True, exist_ok=True)
    (data_dir / "uploads" / "materials" / "videos").mkdir(parents=True, exist_ok=True)
    (data_dir / "uploads" / "materials" / "audios").mkdir(parents=True, exist_ok=True)
    (data_dir / "outputs" / "videos").mkdir(parents=True, exist_ok=True)
    (data_dir / "outputs" / "reports").mkdir(parents=True, exist_ok=True)
    (data_dir / "outputs" / "logs").mkdir(parents=True, exist_ok=True)


def migrate_legacy_if_needed(settings: Settings) -> None:
    """
    Restore legacy DB if user previously ran the single-file version.

    Strategy:
    - If new DB doesn't exist and legacy DB exists at repo root, copy it to data/database.db.
    - Do NOT delete the legacy DB; keep it as a backup.
    """
    repo_root = Path(__file__).resolve().parents[3]
    legacy_db = repo_root / "video_material_system.db"
    new_db = settings.data_dir / "database.db"

    if new_db.exists():
        return

    if legacy_db.exists():
        new_db.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(legacy_db, new_db)


def safe_move(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(src), str(dst))
    except Exception:
        shutil.copy2(str(src), str(dst))


def safe_copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(src), str(dst))


def classify_material_subdir(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext in [".jpg", ".jpeg", ".png", ".bmp", ".webp"]:
        return "images"
    if ext == ".gif":
        return "gifs"
    if ext in [".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"]:
        return "audios"
    if ext in [".mp4", ".mov", ".avi", ".wmv", ".flv", ".mkv"]:
        return "videos"
    return "videos"


def is_safe_relative_path(path_str: str) -> bool:
    p = Path(path_str)
    return not p.is_absolute() and ".." not in p.parts


def normalize_storage_path(path: Path) -> str:
    return path.as_posix()


def resolve_legacy_path(repo_root: Path, path_str: str) -> Path | None:
    if not path_str:
        return None
    p = Path(path_str)
    if p.is_absolute() and p.exists():
        return p
    # Try repo-root relative
    rp = (repo_root / p).resolve()
    if rp.exists():
        return rp
    # Try cwd relative
    cp = Path.cwd() / p
    if cp.exists():
        return cp.resolve()
    return None


def migrate_legacy_paths(settings: Settings) -> None:
    """
    One-time migration:
    - legacy: data/videos, data/subtitles, data/materials, data/output, data/reports
    - new:    data/uploads/* and data/outputs/*

    We COPY files (keep legacy files as backup) and update DB paths to new layout.
    """
    from ..models.database import SessionLocal
    from ..models.material import Material
    from ..models.task import Task

    repo_root = Path(__file__).resolve().parents[3]
    db = SessionLocal()
    try:
        tasks = db.query(Task).all()
        for t in tasks:
            v = resolve_legacy_path(repo_root, t.video_path)
            if v and "uploads/videos" not in v.as_posix():
                dst = settings.data_dir / "uploads" / "videos" / v.name
                if not dst.exists():
                    safe_copy(v, dst)
                t.video_path = normalize_storage_path(dst)

            s = resolve_legacy_path(repo_root, t.subtitle_path)
            if s and "uploads/subtitles" not in s.as_posix():
                dst = settings.data_dir / "uploads" / "subtitles" / s.name
                if not dst.exists():
                    safe_copy(s, dst)
                t.subtitle_path = normalize_storage_path(dst)

            if t.output_path:
                o = resolve_legacy_path(repo_root, t.output_path)
                if o and "outputs/videos" not in o.as_posix():
                    dst = settings.data_dir / "outputs" / "videos" / o.name
                    if not dst.exists():
                        safe_copy(o, dst)
                    t.output_path = normalize_storage_path(dst)

            if t.report_path:
                r = resolve_legacy_path(repo_root, t.report_path)
                if r and "outputs/reports" not in r.as_posix():
                    dst = settings.data_dir / "outputs" / "reports" / r.name
                    if not dst.exists():
                        safe_copy(r, dst)
                    t.report_path = normalize_storage_path(dst)

        materials = db.query(Material).all()
        for m in materials:
            src = resolve_legacy_path(repo_root, m.file_path)
            if not src:
                continue
            subdir = classify_material_subdir(m.file_name)
            dst = settings.data_dir / "uploads" / "materials" / subdir / m.file_name
            if "uploads/materials" not in src.as_posix():
                if not dst.exists():
                    safe_copy(src, dst)
                m.file_path = normalize_storage_path(dst)

        db.commit()
    finally:
        db.close()
