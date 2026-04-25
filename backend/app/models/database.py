from __future__ import annotations

from sqlalchemy import text
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from ..config import Settings


class Base(DeclarativeBase):
    pass


engine = None
SessionLocal = sessionmaker(autocommit=False, autoflush=False)


DEFAULT_PRODUCT_CATALOGS = ["豆包", "抖音精选", "红果app"]


def _ensure_default_material_products(conn) -> None:
    for name in DEFAULT_PRODUCT_CATALOGS:
        conn.execute(
            text(
                "INSERT INTO material_products(name, created_at, updated_at) "
                "SELECT :name, datetime('now'), datetime('now') "
                "WHERE NOT EXISTS (SELECT 1 FROM material_products WHERE name=:name)"
            ),
            {"name": name},
        )


def _ensure_material_relationships(conn) -> None:
    rows = conn.execute(
        text(
            "SELECT id, library_kind, product_name, script_folder "
            "FROM materials ORDER BY id ASC"
        )
    ).fetchall()
    for row in rows:
        material_id = int(row[0])
        library_kind = str(row[1] or "unfiled").strip().lower()
        product_name = str(row[2] or "").strip()
        script_folder = str(row[3] or "").strip()

        if library_kind != "product":
            conn.execute(
                text(
                    "UPDATE materials "
                    "SET library_kind='unfiled', product_id=NULL, script_folder_id=NULL "
                    "WHERE id=:id"
                ),
                {"id": material_id},
            )
            continue

        if not product_name:
            product_name = "未分类产品"
        if not script_folder:
            script_folder = "默认脚本"

        conn.execute(
            text(
                "INSERT INTO material_products(name, created_at, updated_at) "
                "SELECT :name, datetime('now'), datetime('now') "
                "WHERE NOT EXISTS (SELECT 1 FROM material_products WHERE name=:name)"
            ),
            {"name": product_name},
        )
        product_id = conn.execute(
            text("SELECT id FROM material_products WHERE name=:name"),
            {"name": product_name},
        ).scalar_one()

        conn.execute(
            text(
                "INSERT INTO material_script_folders(product_id, name, created_at, updated_at) "
                "SELECT :product_id, :name, datetime('now'), datetime('now') "
                "WHERE NOT EXISTS ("
                "SELECT 1 FROM material_script_folders WHERE product_id=:product_id AND name=:name"
                ")"
            ),
            {"product_id": int(product_id), "name": script_folder},
        )
        script_folder_id = conn.execute(
            text(
                "SELECT id FROM material_script_folders "
                "WHERE product_id=:product_id AND name=:name"
            ),
            {"product_id": int(product_id), "name": script_folder},
        ).scalar_one()

        conn.execute(
            text(
                "UPDATE materials "
                "SET product_name=:product_name, script_folder=:script_folder, "
                "product_id=:product_id, script_folder_id=:script_folder_id "
                "WHERE id=:id"
            ),
            {
                "product_name": product_name,
                "script_folder": script_folder,
                "product_id": int(product_id),
                "script_folder_id": int(script_folder_id),
                "id": material_id,
            },
        )


def _ensure_material_folder_bindings(conn) -> None:
    conn.execute(
        text(
            "CREATE TABLE IF NOT EXISTS material_folder_bindings ("
            "id INTEGER NOT NULL PRIMARY KEY, "
            "material_id INTEGER NOT NULL, "
            "script_folder_id INTEGER NOT NULL, "
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
    )
    conn.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_material_folder_binding "
            "ON material_folder_bindings(material_id, script_folder_id)"
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_material_folder_binding_material "
            "ON material_folder_bindings(material_id)"
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_material_folder_binding_script "
            "ON material_folder_bindings(script_folder_id)"
        )
    )
    conn.execute(
        text(
            "INSERT INTO material_folder_bindings(material_id, script_folder_id, created_at) "
            "SELECT id, script_folder_id, datetime('now') "
            "FROM materials "
            "WHERE script_folder_id IS NOT NULL "
            "AND NOT EXISTS ("
            "SELECT 1 FROM material_folder_bindings b "
            "WHERE b.material_id = materials.id AND b.script_folder_id = materials.script_folder_id"
            ")"
        )
    )


def _needs_material_table_rebuild(conn) -> bool:
    indexes = conn.execute(text("PRAGMA index_list(materials)")).fetchall()
    for index in indexes:
        # columns: seq, name, unique, origin, partial
        index_name = index[1]
        is_unique = int(index[2]) == 1
        is_partial = int(index[4]) == 1 if len(index) > 4 else False
        if not is_unique or is_partial:
            continue
        columns = conn.execute(text(f"PRAGMA index_info({index_name!r})")).fetchall()
        col_names = [col[2] for col in columns]
        if col_names == ["file_name"]:
            return True
    return False


def _rebuild_materials_table(conn) -> None:
    conn.execute(text("DROP TABLE IF EXISTS materials__new"))
    conn.execute(
        text(
            "CREATE TABLE materials__new ("
            "id INTEGER NOT NULL PRIMARY KEY, "
            "file_name VARCHAR(255) NOT NULL, "
            "file_type VARCHAR(20) NOT NULL, "
            "file_size INTEGER NOT NULL, "
            "file_path VARCHAR(512) NOT NULL, "
            "library_kind VARCHAR(20) DEFAULT 'unfiled', "
            "product_name VARCHAR(255), "
            "script_folder VARCHAR(255), "
            "product_id INTEGER, "
            "script_folder_id INTEGER, "
            "audio_removed BOOLEAN, "
            "created_at DATETIME"
            ")"
        )
    )
    conn.execute(
        text(
            "INSERT INTO materials__new("
            "id, file_name, file_type, file_size, file_path, library_kind, "
            "product_name, script_folder, product_id, script_folder_id, audio_removed, created_at"
            ") "
            "SELECT "
            "id, file_name, file_type, file_size, file_path, "
            "COALESCE(library_kind, 'unfiled'), product_name, script_folder, "
            "product_id, script_folder_id, audio_removed, created_at "
            "FROM materials"
        )
    )
    conn.execute(text("DROP TABLE materials"))
    conn.execute(text("ALTER TABLE materials__new RENAME TO materials"))


def _ensure_material_indexes(conn) -> None:
    conn.execute(
        text("CREATE INDEX IF NOT EXISTS ix_materials_id ON materials(id)")
    )
    conn.execute(
        text("CREATE INDEX IF NOT EXISTS ix_materials_file_name ON materials(file_name)")
    )
    conn.execute(
        text("CREATE INDEX IF NOT EXISTS ix_materials_product_id ON materials(product_id)")
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_materials_script_folder_id "
            "ON materials(script_folder_id)"
        )
    )
    conn.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_material_unfiled_file_name "
            "ON materials(file_name) WHERE library_kind='unfiled'"
        )
    )
    conn.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_material_script_file_name "
            "ON materials(script_folder_id, file_name) WHERE script_folder_id IS NOT NULL"
        )
    )


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
        if "keyword_collision_warnings_json" not in column_names:
            conn.execute(
                text("ALTER TABLE task_config_snapshots ADD COLUMN keyword_collision_warnings_json TEXT")
            )
        if "collision_priority_json" not in column_names:
            conn.execute(
                text("ALTER TABLE task_config_snapshots ADD COLUMN collision_priority_json TEXT")
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
            "asr_progress": "INTEGER DEFAULT 0",
            "asr_error": "TEXT",
            "asr_retry_count": "INTEGER DEFAULT 0",
            "asr_retry_max": "INTEGER DEFAULT 3",
            "subtitle_line_count_user": "INTEGER",
            "subtitle_line_count_asr": "INTEGER",
            "asr_model_used": "TEXT",
            "video_duration_seconds": "REAL",
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

        material_columns = conn.execute(text("PRAGMA table_info(materials)")).fetchall()
        material_column_names = {row[1] for row in material_columns}
        if "audio_removed" not in material_column_names:
            conn.execute(text("ALTER TABLE materials ADD COLUMN audio_removed INTEGER"))
        if "library_kind" not in material_column_names:
            conn.execute(
                text("ALTER TABLE materials ADD COLUMN library_kind TEXT DEFAULT 'unfiled'")
            )
        if "product_name" not in material_column_names:
            conn.execute(text("ALTER TABLE materials ADD COLUMN product_name TEXT"))
        if "script_folder" not in material_column_names:
            conn.execute(text("ALTER TABLE materials ADD COLUMN script_folder TEXT"))
        if "product_id" not in material_column_names:
            conn.execute(text("ALTER TABLE materials ADD COLUMN product_id INTEGER"))
        if "script_folder_id" not in material_column_names:
            conn.execute(text("ALTER TABLE materials ADD COLUMN script_folder_id INTEGER"))
        conn.execute(
            text(
                "UPDATE materials SET library_kind='unfiled' "
                "WHERE library_kind IS NULL OR TRIM(library_kind)=''"
            )
        )
        conn.execute(
            text(
                "UPDATE materials SET library_kind='unfiled' "
                "WHERE library_kind='general'"
            )
        )
        conn.execute(
            text(
                "UPDATE materials SET library_kind='unfiled' "
                "WHERE library_kind NOT IN ('general', 'product', 'unfiled')"
            )
        )
        if _needs_material_table_rebuild(conn):
            _rebuild_materials_table(conn)
        _ensure_material_indexes(conn)
        _ensure_default_material_products(conn)
        _ensure_material_relationships(conn)
        _ensure_material_folder_bindings(conn)


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
    from .material_folder_binding import MaterialFolderBinding  # noqa: F401
    from .material_product import MaterialProduct  # noqa: F401
    from .material_script_folder import MaterialScriptFolder  # noqa: F401
    from .rough_cut_project import RoughCutProject  # noqa: F401
    from .settings import SettingsRow  # noqa: F401
    from .source_video_entry import SourceVideoEntry  # noqa: F401
    from .task import Task  # noqa: F401
    from .task_snapshot import TaskConfigSnapshot  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_schema_compatibility()
