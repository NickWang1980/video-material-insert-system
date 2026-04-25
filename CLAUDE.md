# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This System Does

Video Material Insert System — a short-form video production platform. Core flows:

1. **Source videos** uploaded → ASR auto-generates subtitles (background, non-blocking)
2. **Material library** organizes clips/images by product → script folder hierarchy
3. **Templates** define keyword-matching rules with 5×5 position selectors and collision priority
4. **Tasks** combine source video + templates → FFmpeg auto-inserts materials → MP4/XLSX output
5. **Rough-cut projects** handle multi-role (actor A/B/C) editing with independent ASR per asset, script splitting, timeline generation, and preview rendering

## Development Commands

### Backend

```bash
# Install dependencies
pip install -r backend/requirements.txt

# Run dev server (from project root)
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest backend/tests/

# Run single test file
pytest backend/tests/test_task_service.py -v
```

### Frontend

```bash
cd frontend
npm install
npm run dev      # dev server at http://localhost:5173
npm run build    # production build → frontend/dist/
```

### Full Stack

```bash
# Dev (frontend on :5173, backend on :8000, Vite proxies /api)
scripts/start_all.bat          # Windows
./scripts/start_all.sh         # Linux/Mac

# Production (backend serves built frontend at :8000)
scripts/start_all.bat --prod
./scripts/start_all.sh --prod
```

### Environment

Copy `backend/.env.example` → `backend/.env`. Key vars: `HOST`, `PORT`, `DATA_DIR`, `FFMPEG_BIN`, `FFPROBE_BIN`. Defaults work for local dev. FFmpeg must be on PATH or configured explicitly.

## Architecture

### Frontend–Backend Separation

- **Dev**: Vite (`:5173`) proxies `/api/*` → FastAPI (`:8000`)
- **Prod**: `npm run build` outputs to `frontend/dist/`; FastAPI serves it via `StaticFiles` mount at `/`

API prefix is always `/api`. Frontend in `frontend/src/api/` are thin Axios wrappers matching this prefix.

### Backend Layout

```
backend/
  main.py              # FastAPI app, startup hooks, static file mount
  app/
    api/               # Route handlers (one file per domain)
    models/            # SQLAlchemy ORM models
    schemas/           # Pydantic request/response models
    services/          # Business logic (heavy lifting here)
    utils/             # FFmpeg command builders, file path helpers, SRT utils
    config.py          # Settings dataclass, .env loading
    dependencies.py    # FastAPI DI (DB session, etc.)
```

Key services:
- `task_service.py` — task execution, FFmpeg orchestration, concurrency semaphore (max 2 concurrent jobs)
- `asr_service.py` — Whisper (faster-whisper) integration, background thread scheduling
- `material_service.py` — keyword matching, collision detection/resolution
- `rough_cut_service.py` — script splitting, per-role ASR, timeline building, preview generation

### Database

SQLite via SQLAlchemy 2.x. Heavy use of **JSON columns** for flexible data (sentences, roles, assets, timeline arrays). Schema migrations live in `_ensure_schema_compatibility()` in `backend/app/models/database.py` — always add backward-compat migration there when changing models rather than dropping/recreating tables.

### Data Directory

All files in `/data/` (relative to project root, configurable via `DATA_DIR`):

```
data/
  database.db
  source_videos/          # uploaded source videos
  source_videos_asr/      # Whisper-generated SRT + extracted WAV/FLAC
  source_videos_subtitles/ # user-uploaded SRT files
  materials/              # material clips (images, GIFs, videos)
  tasks/                  # task output (MP4, XLSX, TXT)
  rough_cut_projects/     # rough-cut workspace outputs
  uploads/                # temp upload staging
```

### Key Architectural Patterns

**Dual subtitle sources**: Each source video can have both a user-uploaded SRT and an ASR-generated SRT. Task creation lets the user choose which to use.

**Template collision priority**: When multiple keywords match the same timestamp, resolution uses proximity + user-defined layer priority (lower layer index = higher override priority). Collision warnings are stored on the task at creation time, not at execution time.

**Rough-cut asset independence**: Each asset (video file) in a rough-cut project gets its own ASR run. The service then matches ASR segments to script sentences per role. Timeline is rebuilt from matched segments.

**File path normalization**: `backend/app/utils/file_utils.py` handles cross-platform path normalization — always use these utils when constructing or storing file paths, not raw `os.path` joins.

**OpenCC**: Used for Simplified Chinese text normalization of ASR output. Applied before keyword matching.

## Common Change Patterns

**Add an API endpoint**: Route handler in `backend/app/api/` → Pydantic schema in `backend/app/schemas/` → service logic in `backend/app/services/` → register router in `backend/main.py` → API wrapper in `frontend/src/api/`

**Change database schema**: Edit SQLAlchemy model → add `ALTER TABLE` migration to `_ensure_schema_compatibility()` in `database.py`

**Change material matching logic**: `backend/app/services/material_service.py` for matching; `backend/app/services/task_service.py` for collision handling during task execution
