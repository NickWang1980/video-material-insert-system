from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from .app.api.auth import router as auth_router
from .app.api.audit import router as audit_router
from .app.api.roles import router as roles_router
from .app.api.users import router as users_router
from .app.api.configs import router as configs_router
from .app.api.materials import router as materials_router
from .app.api.rough_cut import router as rough_cut_router
from .app.api.settings import router as settings_router
from .app.api.source_videos import router as source_videos_router
from .app.api.stats import router as stats_router
from .app.api.tasks import router as tasks_router
from .app.middleware.audit_middleware import AuditMiddleware
from .app.middleware.auth_middleware import AuthMiddleware
from .app.config import get_settings
from .app.models.database import init_db
from .app.utils.file_utils import (
    ensure_data_layout,
    migrate_legacy_if_needed,
    migrate_legacy_paths,
)
from .app.utils.logger import configure_logging
from .app.services.task_service import resume_all_tasks
from .app.services.asr_service import resume_pending_asr_jobs


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()

    app = FastAPI(title="短视频智能素材自动植入系统 API", version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(AuditMiddleware)
    # AuthMiddleware runs first (added last = outermost)
    app.add_middleware(AuthMiddleware)

    @app.on_event("startup")
    def _startup() -> None:
        ensure_data_layout(settings)
        migrate_legacy_if_needed(settings)
        init_db(settings)
        migrate_legacy_paths(settings)
        # Resume all unfinished tasks after restart.
        resume_all_tasks(settings, include_failed=True)
        # Resume ASR jobs for pending/running/retryable-failed source videos.
        resume_pending_asr_jobs(settings)

    app.include_router(auth_router)
    app.include_router(audit_router)
    app.include_router(roles_router)
    app.include_router(users_router)
    app.include_router(tasks_router)
    app.include_router(rough_cut_router)
    app.include_router(configs_router)
    app.include_router(materials_router)
    app.include_router(source_videos_router)
    app.include_router(settings_router)
    app.include_router(stats_router)

    # Production static hosting: mount frontend/dist if present
    repo_root = Path(__file__).resolve().parents[1]
    dist_dir = repo_root / "frontend" / "dist"
    if dist_dir.exists():
        app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="frontend")

    return app


app = create_app()
