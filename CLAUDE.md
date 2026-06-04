# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This System Does

Video Material Insert System — a short-form video production platform. Core flows:

1. **Source videos** uploaded → ASR auto-generates subtitles (background, non-blocking)
2. **Material library** organizes clips/images by product → script folder hierarchy
3. **Templates** define keyword-matching rules with 5×5 position selectors and collision priority
4. **Tasks** combine source video + templates → FFmpeg auto-inserts materials → MP4/XLSX output
5. **Rough-cut projects** handle multi-role (actor A/B/C) editing with independent ASR per asset, script splitting, timeline generation, and preview rendering
6. **TTS Studio** (Qwen3-TTS) — text-to-speech with voice cloning, preset voices, batch synthesis (.txt → zip), localStorage history, and "save to material library" hand-off
7. **视频生产 (Video Production)** — 控制台侧栏顶级分组，集合「文案生成」「语音生成」「视频生成」三个上游模块。语音生成复用 `/tts`；视频生成 Phase-1 已上线（见第 9 条，对接 heygem 数字人引擎 sidecar）；文案生成已在 Phase-1 实装为完整模块（见第 8 条），与下游「混剪」「素材插入」共同构成端到端蛇形工作流（控制台首页 9 步流程图）。
8. **文案生成 (Copy Gen)** — Phase-1 已上线：基于 OpenAI-compatible LLM 的中文短视频口播文案生成器。包含 10 个文案模板（problem_countermeasure / comparison_case / challenge_record / myth_truth / story_insight / data_analysis / product_scenario / hotspot_connection / suspense_reveal / welfare_urgency）、4 个平台 tone（抖音/小红书/快手/视频号）、两种脚本类型（single / ab_role）、Agent 系统（规则 + 知识库 + 默认参数 + 绑定 ModelConfig）、多模型配置 CRUD（api_key Fernet 加密落库）、生成结果用 Qwen3-TTS `content|emotion|speed` 行格式输出、一键按行送 `POST /api/tts/synthesize`。前端 `/copy-gen`，后端 `/api/copy-gen/*`。
9. **视频生成 (Video Gen)** — Phase-1 已上线：以 inline 子目录形式纳管 heygem 数字人引擎（`vendor/heygem`，原 git submodule 已在 2026-05-22 inline 进主仓，简化 clone / push 流程）。便携 py39 (~13 GB) + ~750 MB 模型权重 + 部分 .pyc 反编译模块均不进 git（`.gitignore` 双层覆盖），需用户在每台机器首次部署时通过 robocopy 自带的 py39 / 权重目录补齐，或设 `HEYGEM_PY39_DIR` 环境变量指向已有的便携 Python 3.10 安装。heygem 仍作 sidecar 运行，不可与 master venv 合并。`vendor/heygem/api_server.py` 暴露 REST（`POST /api/heygem/synthesize` multipart audio+video → work_id；`GET /status/{id}`；`GET /result/{id}`；`GET /health`），由 `vendor/heygem/start_api.bat` 启动到 `:8383`（首次自动 pip 装 fastapi/uvicorn/python-multipart 到便携 py39）。master 后端 `/api/video-gen/*` 用 httpx 调；`VideoGenTask` 落库；后台 daemon thread 3s 轮询 `/status`，终态时把 mp4 流式落到 `data/video_gen/{id}.mp4`。前端 `/video-gen` 三列布局（音频源三选一：上传/TTS 历史/素材库；参考视频源三选一：上传/source_videos/素材库；任务面板含进度条 / 预览 / 下载 / 「保存到素材库」）。一键启动用 `scripts/start_all.bat --with-heygem`（不带开关则只起 master）。显存策略 Phase-1 仅"manual"（用户自己保证 TTS 与 heygem 不同时跑），Settings 页留下拉做 tts_unload / cuda_isolate 的 Phase-2 埋点（仅写 localStorage）。后端重启时未完成任务标记 `interrupted`（Phase-1 不自动续跑）。

## Development Commands

### Backend

**Requires Python 3.12+** (enforced by `scripts/precheck.sh`; qwen_tts / torch / faster-whisper / cryptography wheels are 3.12+ only — 3.11 falls back to source builds and fails).

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

Frontend stack: **Vue 3 + Vite + Pinia + Vue Router + Element Plus + TailwindCSS + vue-i18n**. There is **no ESLint / Prettier / Vitest / TypeScript** config — the only npm scripts are `dev`, `build`, `preview`. The `start_all` scripts detect a stale `node_modules` by probing for ~7 key packages (not lockfile integrity), so run `npm install` manually after changing frontend dependencies.

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
- `tts_service.py` — Qwen3-TTS lazy loader (Base / CustomVoice), threading-safe model cache, idle-unload watchdog, tqdm-hooked progress reporting; routes synthesis to `generate_voice_clone` or `generate_custom_voice` based on payload

### Auth, RBAC & Audit

The app is gated by a JWT auth layer wired as FastAPI middleware in `backend/main.py` (order: `AuthMiddleware` → `AuditMiddleware` → CORS). `AuthMiddleware` validates the bearer token (`auth_service.py`, PyJWT + bcrypt) on protected routes; `AuditMiddleware` records mutating requests to the `AuditLog` table. Domain split:

- `auth.py` — login, `/me`, token issuance
- `users.py` — admin-only user CRUD; `roles.py` — `RoleDefinition` catalog (also feeds rough-cut role traits)
- `audit.py` — audit-log read/purge

Frontend mirrors this: `store/modules/auth.js` holds login state + `isAdmin`; the `router/index.js` `beforeEach` guard redirects unauthenticated users to `/login` and blocks admin routes (`/admin/users`) when `!auth.isAdmin`. Sidebar entries filter on `moduleKey` permissions. `jwt_secret` defaults to a dev value — override in prod.

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
  outputs/tts/            # TTS-generated WAV files (served via /api/tts/audio/{name})
  qwen3_models/           # HuggingFace / ModelScope cache for Qwen3-TTS weights
  uploads/                # temp upload staging
  uploads/tts_refs/       # uploaded reference audio for voice cloning
```

### Key Architectural Patterns

**Dual subtitle sources**: Each source video can have both a user-uploaded SRT and an ASR-generated SRT. Task creation lets the user choose which to use.

**Template collision priority**: When multiple keywords match the same timestamp, resolution uses proximity + user-defined layer priority (lower layer index = higher override priority). Collision warnings are stored on the task at creation time, not at execution time.

**Rough-cut asset independence**: Each asset (video file) in a rough-cut project gets its own ASR run. The service then matches ASR segments to script sentences per role. Timeline is rebuilt from matched segments.

**File path normalization**: `backend/app/utils/file_utils.py` handles cross-platform path normalization — always use these utils when constructing or storing file paths, not raw `os.path` joins.

**OpenCC**: Used for Simplified Chinese text normalization of ASR output. Applied before keyword matching.

**TTS lazy-loading**: `tts_service.py` keeps a `(model_id, device, dtype)`-keyed cache; `get_or_load_tts()` is concurrent-safe via per-key `threading.Event`. The first synthesis or `/api/tts/load` triggers model download (~1.7 GB Base, optional ~1.7 GB CustomVoice). An idle-unload watchdog (`tts_idle_unload_minutes`, default 15) frees ~7 GB RAM/VRAM after inactivity. Progress is monkey-patched into `tqdm` (`tqdm_progress_hook.py`) so the frontend's 2 s polling on `/api/tts/status` shows download percentage.

**CUDA runtime precheck**: `scripts/precheck.sh` 第 4.5 段在检测到 NVIDIA 驱动时，用 `ctypes` 试加载 `cudart64_12.dll` / `cublas64_12.dll` / `cublasLt64_12.dll` / `cudnn64_9.dll`（或 cuDNN 8 等价物）等 CTranslate2 4.x + torch CUDA 必需的运行时 DLL，并打印 `ctranslate2.get_cuda_device_count()` 与 `torch.cuda.is_available()`。任一缺失只 `log_warn`（不阻断启动），并给出"int8 绕过 / pip nvidia-cublas-cu12 / 装 CUDA Toolkit"三种解决方向。这是为了拦截"装了 NVIDIA 驱动但未装 CUDA Toolkit / cuDNN"导致的 ASR float16 模式 `cublas64_12.dll not found` 启动期假阳性。

**日志查看器**：`backend/app/utils/logger.py` 用 loguru 维护 5 个文件 sink + 1 个 stdlib bridge：`asr_{time}.log`（filter: `asr_service`）、`tts_{time}.log`（filter: `tts_service` / `app.api.tts`）、`copy_gen_{time}.log`（filter: `copy_gen`，**含 LLM request body / response body / usage tokens**）、`video_gen_{time}.log`（filter: `video_service`）、`app_{time}.log`（其余）。`copy_gen` 全部走 stdlib `logging.getLogger(__name__)`，由 `_InterceptHandler` 桥接进 loguru。前端 `LogsViewer.vue` 通过 `GET /api/logs/categories` 动态拿 tab，所以新增类别只需改 `log_viewer_service._FILE_CATEGORIES`。要为新增模块单独归档日志，按上面 filter 增加一个 loguru sink + 在 log_viewer 的 `_FILE_CATEGORIES` 注册 `(key, label, glob)` 即可。

**TTS frontend** (`frontend/src/views/TTSStudio.vue` + `frontend/src/components/tts/*`): single page combining model status bar, text/parameter form (language / emotion / instruct / speed), two-mode tabs (voice clone vs preset speaker), result audio player, history sidebar (localStorage `vmis_tts_history`, ≤50 entries), batch panel (.txt → JSZip client-side packaging), and "save to material library" dialog (uploads the WAV via `POST /api/materials`). Locale switching (zh-CN / en-US) is scoped to TTS UI only — see `frontend/src/locale/`.

## Common Change Patterns

**Add an API endpoint**: Route handler in `backend/app/api/` → Pydantic schema in `backend/app/schemas/` → service logic in `backend/app/services/` → register router in `backend/main.py` → API wrapper in `frontend/src/api/`

**Change database schema**: Edit SQLAlchemy model → add `ALTER TABLE` migration to `_ensure_schema_compatibility()` in `database.py`

**Add / change UI text**: locale JSON lives in `frontend/src/locale/{zh-CN,en-US}/`. Always add the key to **both** locales with matching structure — vue-i18n keys must stay in sync or the other locale falls back / shows the raw key.

**Change material matching logic**: `backend/app/services/material_service.py` for matching; `backend/app/services/task_service.py` for collision handling during task execution

**Change TTS behavior**: backend in `backend/app/services/tts_service.py` (lazy load, synth routing) and `backend/app/api/tts.py` (REST). Frontend page at `frontend/src/views/TTSStudio.vue` with sub-components in `frontend/src/components/tts/`; API wrapper `frontend/src/api/tts.js`; Pinia store `frontend/src/store/modules/tts.js` (status polling, enums cache, history). Locale strings in `frontend/src/locale/{zh-CN,en-US}/tts.json` — keep keys in sync between the two files.

**Add a sidebar entry / workflow step**: 侧栏顶级条目在 `frontend/src/components/layout/Sidebar.vue` 的 `allItems` 中定义（带 `moduleKey` 用于权限过滤；分组项含 `key` + `children`，展开状态持久化在 `localStorage["vmis_sidebar_groups"]`）。控制台首页工作流程图在 `frontend/src/views/Home.vue`，采用 9 步蛇形 grid 布局（`.flow-row` + `.flow-connector` + `.flow-down`）：第一行 ①→②→③→④（文案 → 语音 → 视频 → 混剪），第二行 ⑧←⑦←⑥←⑤（任务 ← 源视频 ← 模板 ← 素材），第三行 ⑨（下载产物）。新增步骤时同步更新 `Home.vue` 的 3 行 grid 与 Sidebar 的「视频生产」分组。`/voice-gen` redirect → `/tts` 以避免与现有 TTS 重复。

**Change Video Gen behavior**: 后端 `backend/app/services/video_gen_service.py`（httpx 客户端单例 / source 解析 / submit_and_poll 后台线程 / save_to_material_library）+ `backend/app/api/video_gen.py`（multipart create + list/detail/cancel/download/save-to-material/health）+ `backend/app/models/video_gen.py` model（VideoGenTask）+ `backend/app/schemas/video_gen.py` Pydantic + `backend/app/config.py` 的 4 个字段（heygem_base_url / heygem_enabled / heygem_request_timeout / video_gen_vram_strategy）+ `backend/.env.example` 同步。前端页面 `frontend/src/views/VideoGen.vue` + 4 个子组件 `frontend/src/components/videoGen/{AudioSourcePicker,VideoSourcePicker,VideoGenStatusBar,SaveVideoToMaterialDialog}.vue`；API wrapper `frontend/src/api/videoGen.js`；Pinia store `frontend/src/store/modules/videoGen.js`（localStorage key `vmis_video_gen_vram_strategy`）。Settings 页「视频生成 / heygem 数字人 sidecar」section 集中显示连接状态 + VRAM 策略下拉。heygem 端的改动直接在 `vendor/heygem/` 子目录里改 + 在主仓一次 commit 即可（已不是 submodule，无需双推），常见入口 `vendor/heygem/api_server.py`（REST 薄壳） + `vendor/heygem/start_api.bat`（启动器；只查找 `./py39/python.exe` 或 `HEYGEM_PY39_DIR`）。`vendor/heygem/.gitignore` 仍作为 nested gitignore 生效，覆盖 `py39/`、`tmp/`、`result/`、`audio/`、各模型权重目录与 `*.pth/*.pt/*.onnx/...` 后缀。日志类别复用 `video_gen_*.log`（`_VIDEO_GEN_KEYS` 已包含 `video_gen_service` 与 `app.api.video_gen`）。

**Change Copy Gen behavior**: 后端服务分散在 `backend/app/services/copy_gen/`（`templates.py` 文案模板 / `voice_config.py` Qwen3-TTS 解析 / `llm_client.py` LLM 客户端包装（默认 OpenAI-compatible SDK，亦内置 `anthropic` SDK，按 ModelConfig 的 base_url 自动路由）/ `model_config_service.py` Fernet 加解密 + 测连通 / `agent_service.py` Agent + Rule + Knowledge CRUD + `build_system_prompt` / `generator_service.py` 顺序多版本生成入口）；REST 在 `backend/app/api/copy_gen.py`；模型在 `backend/app/models/copy_gen.py`；Pydantic 在 `backend/app/schemas/copy_gen.py`。前端页面 `frontend/src/views/CopyGen.vue` + 9 个子组件 `frontend/src/components/copyGen/{QuickGenerator,AgentManager,AgentDetail,RuleEditor,KnowledgeEditor,ModelConfigManager,ResultCard,SendToTTSDialog,HistoryList}.vue`；API wrapper `frontend/src/api/copyGen.js`；Pinia store `frontend/src/store/modules/copyGen.js`（localStorage key `vmis_copygen_history`，≤50 条 quota-trim）；locale `frontend/src/locale/{zh-CN,en-US}/copyGen.json`（同 372 leaf key 结构对齐）。Fernet 加密 key 解析优先级：`settings.copy_gen_llm_key` 环境变量 → `data/.copy_gen_key` 文件 → 自动生成并写入。Phase-1 不含文档解析 / 从范例学习 / 整合优化 / 多用户 Agent 隔离 — 见 `docs/20260515_copy_gen_phase1_*.md`。
