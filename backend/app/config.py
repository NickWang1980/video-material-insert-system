from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    database_url: str
    data_dir: Path
    ffmpeg_bin: str
    ffprobe_bin: str


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is not None:
        return _settings

    # Load .env from backend/ if present, else repo root.
    backend_dir = Path(__file__).resolve().parents[1]
    repo_root = backend_dir.parent
    load_dotenv(backend_dir / ".env", override=False)
    load_dotenv(repo_root / ".env", override=False)

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    database_url = os.getenv("DATABASE_URL", "sqlite:///./data/database.db")
    data_dir_env = os.getenv("DATA_DIR", str(repo_root / "data"))
    data_dir = Path(data_dir_env).resolve()
    ffmpeg_bin = os.getenv("FFMPEG_BIN", "ffmpeg")
    ffprobe_bin = os.getenv("FFPROBE_BIN", "ffprobe")

    # Normalize sqlite path to be repo-root-relative when using the default ./data path.
    if database_url.startswith("sqlite:///./"):
        rel = database_url.removeprefix("sqlite:///./")
        database_url = f"sqlite:///{(repo_root / rel).resolve().as_posix()}"

    _settings = Settings(
        host=host,
        port=port,
        database_url=database_url,
        data_dir=data_dir,
        ffmpeg_bin=ffmpeg_bin,
        ffprobe_bin=ffprobe_bin,
    )
    return _settings
