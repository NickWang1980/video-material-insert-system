from __future__ import annotations

from sqlalchemy import text
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from ..config import Settings


class Base(DeclarativeBase):
    pass


engine = None
SessionLocal = sessionmaker(autocommit=False, autoflush=False)


def _ensure_schema_compatibility() -> None:
    if engine is None:
        return
    if not str(engine.url).startswith("sqlite"):
        return

    with engine.begin() as conn:
        columns = conn.execute(text("PRAGMA table_info(task_config_snapshots)")).fetchall()
        column_names = {row[1] for row in columns}
        if "source_templates_json" not in column_names:
            conn.execute(
                text("ALTER TABLE task_config_snapshots ADD COLUMN source_templates_json TEXT")
            )

        task_columns = conn.execute(text("PRAGMA table_info(tasks)")).fetchall()
        task_column_names = {row[1] for row in task_columns}
        if "source_entry_id" not in task_column_names:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN source_entry_id INTEGER"))
        if "subtitle_source" not in task_column_names:
            conn.execute(
                text("ALTER TABLE tasks ADD COLUMN subtitle_source TEXT DEFAULT 'uploaded'")
            )
        if "add_subtitle_to_video" not in task_column_names:
            conn.execute(
                text("ALTER TABLE tasks ADD COLUMN add_subtitle_to_video INTEGER DEFAULT 0")
            )

        source_columns = conn.execute(text("PRAGMA table_info(source_video_entries)")).fetchall()
        source_column_names = {row[1] for row in source_columns}
        source_column_defs = {
            "audio_wav_path": "TEXT",
            "audio_flac_path": "TEXT",
            "asr_srt_path": "TEXT",
            "asr_status": "TEXT DEFAULT 'pending'",
            "asr_error": "TEXT",
            "asr_retry_count": "INTEGER DEFAULT 0",
            "asr_retry_max": "INTEGER DEFAULT 3",
            "subtitle_line_count_user": "INTEGER",
            "subtitle_line_count_asr": "INTEGER",
            "asr_model_used": "TEXT",
        }
        for name, ddl_type in source_column_defs.items():
            if name not in source_column_names:
                conn.execute(
                    text(f"ALTER TABLE source_video_entries ADD COLUMN {name} {ddl_type}")
                )

        settings_columns = conn.execute(text("PRAGMA table_info(settings)")).fetchall()
        settings_column_names = {row[1] for row in settings_columns}
        if "asr_model" not in settings_column_names:
            conn.execute(
                text("ALTER TABLE settings ADD COLUMN asr_model TEXT DEFAULT 'small'")
            )


def init_db(settings: Settings) -> None:
    global engine
    if engine is not None:
        return

    connect_args = {}
    if settings.database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}

    engine = create_engine(settings.database_url, connect_args=connect_args)
    SessionLocal.configure(bind=engine)

    from .config_template import ConfigTemplate  # noqa: F401
    from .material import Material  # noqa: F401
    from .settings import SettingsRow  # noqa: F401
    from .source_video_entry import SourceVideoEntry  # noqa: F401
    from .task import Task  # noqa: F401
    from .task_snapshot import TaskConfigSnapshot  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_schema_compatibility()
