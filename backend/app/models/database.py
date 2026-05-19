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


def _ensure_default_roles(conn) -> None:
    import json as _json
    from ..schemas.role import ADMIN_MODULE_KEYS, DEFAULT_USER_MODULE_KEYS  # noqa: PLC0415
    defaults = [
        ("admin", "管理员", 1, ADMIN_MODULE_KEYS),
        ("user", "普通用户", 1, DEFAULT_USER_MODULE_KEYS),
    ]
    for name, display_name, is_system, expected_keys in defaults:
        row = conn.execute(
            text("SELECT id, module_keys FROM role_definitions WHERE name=:n"), {"n": name}
        ).fetchone()
        if not row:
            conn.execute(
                text(
                    "INSERT INTO role_definitions(name, display_name, is_system, module_keys, created_at) "
                    "VALUES(:n, :d, :s, :m, datetime('now'))"
                ),
                {"n": name, "d": display_name, "s": is_system, "m": _json.dumps(expected_keys)},
            )
        else:
            # Merge in any newly-added module keys so existing DBs stay up to date
            try:
                current = _json.loads(row[1]) if isinstance(row[1], str) else (row[1] or [])
            except Exception:
                current = []
            merged = list(current) + [k for k in expected_keys if k not in current]
            if merged != current:
                conn.execute(
                    text("UPDATE role_definitions SET module_keys=:m WHERE id=:id"),
                    {"m": _json.dumps(merged), "id": row[0]},
                )


def _ensure_default_users(conn) -> None:
    import bcrypt as _bcrypt  # noqa: PLC0415
    defaults = [
        ("admin", "admin123", "admin"),
        ("user", "user123", "user"),
    ]
    for username, password, role in defaults:
        exists = conn.execute(
            text("SELECT 1 FROM users WHERE username=:u"), {"u": username}
        ).scalar()
        if not exists:
            pw_hash = _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()
            conn.execute(
                text(
                    "INSERT INTO users(username, password_hash, role, is_active, created_at) "
                    "VALUES(:u, :h, :r, 1, datetime('now'))"
                ),
                {"u": username, "h": pw_hash, "r": role},
            )


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
        if "asr_compute_type" not in settings_column_names:
            conn.execute(
                text("ALTER TABLE settings ADD COLUMN asr_compute_type TEXT DEFAULT 'auto'")
            )
        if "video_encoder_mode" not in settings_column_names:
            conn.execute(
                text("ALTER TABLE settings ADD COLUMN video_encoder_mode TEXT DEFAULT 'auto'")
            )

        # ── source_video_entries: asr_compute_type_used ───────────────
        if "asr_compute_type_used" not in source_column_names:
            conn.execute(
                text("ALTER TABLE source_video_entries ADD COLUMN asr_compute_type_used TEXT")
            )

        # ── tasks: 4 个执行环境字段 ──────────────────────────────────
        task_columns = conn.execute(text("PRAGMA table_info(tasks)")).fetchall()
        task_column_names = {row[1] for row in task_columns}
        for col, ddl in [
            ("asr_model_used", "TEXT"),
            ("asr_compute_type_used", "TEXT"),
            ("video_encoder_used", "TEXT"),
            ("video_resolution_used", "TEXT"),
        ]:
            if col not in task_column_names:
                conn.execute(text(f"ALTER TABLE tasks ADD COLUMN {col} {ddl}"))

        # ── rough_cut_projects: 4 个执行环境字段 ─────────────────────
        rcp_columns = conn.execute(text("PRAGMA table_info(rough_cut_projects)")).fetchall()
        rcp_column_names = {row[1] for row in rcp_columns}
        for col, ddl in [
            ("asr_model_used", "TEXT"),
            ("asr_compute_type_used", "TEXT"),
            ("video_encoder_used", "TEXT"),
            ("video_resolution_used", "TEXT"),
        ]:
            if col not in rcp_column_names:
                conn.execute(text(f"ALTER TABLE rough_cut_projects ADD COLUMN {col} {ddl}"))

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
        # users table
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS users ("
            "id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, "
            "username VARCHAR(100) NOT NULL UNIQUE, "
            "password_hash VARCHAR(255) NOT NULL, "
            "role VARCHAR(20) NOT NULL DEFAULT 'user', "
            "is_active INTEGER NOT NULL DEFAULT 1, "
            "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"
            ")"
        ))
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users(username)"
        ))
        _ensure_default_users(conn)

        # role_definitions table
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS role_definitions ("
            "id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, "
            "name VARCHAR(50) NOT NULL UNIQUE, "
            "display_name VARCHAR(100) NOT NULL, "
            "is_system INTEGER NOT NULL DEFAULT 0, "
            "module_keys TEXT NOT NULL DEFAULT '[]', "
            "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"
            ")"
        ))
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_role_definitions_name ON role_definitions(name)"
        ))
        _ensure_default_roles(conn)

        # audit_logs table (CREATE IF NOT EXISTS covers new installs;
        # ALTER TABLE handles existing DBs that pre-date this feature)
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS audit_logs ("
            "id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, "
            "method VARCHAR(10) NOT NULL, "
            "path VARCHAR(512) NOT NULL, "
            "action VARCHAR(200) NOT NULL, "
            "entity_type VARCHAR(50), "
            "entity_id VARCHAR(50), "
            "status_code INTEGER NOT NULL DEFAULT 0, "
            "ip_address VARCHAR(45), "
            "user_agent VARCHAR(512), "
            "operator VARCHAR(100), "
            "source VARCHAR(20) NOT NULL DEFAULT 'user', "
            "duration_ms INTEGER, "
            "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"
            ")"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at ON audit_logs(created_at)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_audit_logs_entity_type ON audit_logs(entity_type)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_audit_logs_operator ON audit_logs(operator)"
        ))
        audit_cols = {r[1] for r in conn.execute(text("PRAGMA table_info(audit_logs)")).fetchall()}
        if "source" not in audit_cols:
            conn.execute(text("ALTER TABLE audit_logs ADD COLUMN source VARCHAR(20) NOT NULL DEFAULT 'user'"))
        if "duration_ms" not in audit_cols:
            conn.execute(text("ALTER TABLE audit_logs ADD COLUMN duration_ms INTEGER"))

        if _needs_material_table_rebuild(conn):
            _rebuild_materials_table(conn)
        _ensure_material_indexes(conn)
        _ensure_default_material_products(conn)
        _ensure_material_relationships(conn)
        _ensure_material_folder_bindings(conn)


def _make_engine(settings: Settings):
    url = settings.database_url
    key = settings.db_encryption_key.strip()

    if key and url.startswith("sqlite"):
        try:
            import sqlcipher3.dbapi2 as sqlcipher  # type: ignore

            raw_path = url.replace("sqlite:///", "").lstrip("/")
            import os as _os
            db_path = _os.path.abspath(raw_path)
            safe_key = key.replace("'", "''")

            def _creator():
                conn = sqlcipher.connect(db_path)
                conn.execute(f"PRAGMA key='{safe_key}'")
                conn.execute("PRAGMA foreign_keys=ON")
                return conn

            import logging as _log
            _log.getLogger(__name__).info("Database encryption enabled (SQLCipher).")
            return create_engine("sqlite://", creator=_creator)
        except ImportError:
            import logging as _log
            _log.getLogger(__name__).warning(
                "DB_ENCRYPTION_KEY is set but sqlcipher3 is not installed — "
                "running unencrypted. Install sqlcipher3-binary to enable encryption."
            )

    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args)


def init_db(settings: Settings) -> None:
    global engine
    if engine is not None:
        return

    engine = _make_engine(settings)
    SessionLocal.configure(bind=engine)

    from .audit_log import AuditLog  # noqa: F401
    from .role_definition import RoleDefinition  # noqa: F401
    from .config_template import ConfigTemplate  # noqa: F401
    from .user import User  # noqa: F401
    from .material import Material  # noqa: F401
    from .material_folder_binding import MaterialFolderBinding  # noqa: F401
    from .material_product import MaterialProduct  # noqa: F401
    from .material_script_folder import MaterialScriptFolder  # noqa: F401
    from .rough_cut_project import RoughCutProject  # noqa: F401
    from .settings import SettingsRow  # noqa: F401
    from .source_video_entry import SourceVideoEntry  # noqa: F401
    from .task import Task  # noqa: F401
    from .task_snapshot import TaskConfigSnapshot  # noqa: F401
    from .copy_gen import (  # noqa: F401
        CopyGenAgent,
        CopyGenHistory,
        CopyGenKnowledge,
        CopyGenModelConfig,
        CopyGenRule,
    )
    from .video_gen import VideoGenTask  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_schema_compatibility()
