# 视频生成模块 Phase-1 集成 heygem — 实施 Changelog

- 完成时间：2026-05-17 04:11
- 计划文档：[`docs/20260517_0307_video_gen_phase1_plan.md`](20260517_0307_video_gen_phase1_plan.md)
- 工时实际：约 1.5 小时（不含用户验收）
- 实施者：Claude，Nicholas 协作

---

## 决策确认（与计划一致）

| 议题 | 已落地 |
|---|---|
| 集成形态 | 独立 HTTP sidecar（master 用 httpx 调） ✅ |
| heygem 位置 | `vendor/heygem` 作为 git submodule，远端用 `file:///D:/workspace/bzybox/v-project/heygem_win_no_docker_50_v2` 过渡 ✅ |
| 显存策略 | Phase-1 仅"manual" 生效；Settings 页留 dropdown + localStorage 偏好 ✅ |
| 音频源 | upload + TTS 历史（localStorage `vmis_tts_history`）+ 素材库 audio ✅ |
| 参考视频源 | upload + `source_videos` + 素材库 video ✅ |

---

## 改动清单

### A. heygem 端（submodule 内部）

新增（在源 heygem 仓库 commit，SHA `2674093`）：

- `vendor/heygem/api_server.py` — FastAPI 薄壳，单 process / 单 TransDhTask 单例，3 个端点：
  - `POST /api/heygem/synthesize` (multipart audio_file + video_file) → `{work_id}`
  - `GET /api/heygem/status/{work_id}` → `{phase, percent, completed, success, error, ...}`
  - `GET /api/heygem/result/{work_id}` → FileResponse(mp4)
  - `GET /api/heygem/health` → `{ready, gpu, version, init_error}`
- `vendor/heygem/start_api.bat` — 复刻 `一键运行.bat` 的环境变量，但末行替换为 `uvicorn api_server:app --host 0.0.0.0 --port 8383`；首次启动会自检并 pip 装 fastapi/uvicorn/python-multipart 到便携 py39
- `vendor/heygem/.gitignore` — 排除 py39 / tmp / result / audio / data/temp / data/log / hf_download / tf_download / __pycache__（保留顶层 `.pyc` 因其为反编译源）

### B. master 后端

**新文件**：
- `backend/app/models/video_gen.py` — `VideoGenTask` ORM（17 列；audio_source_type / video_source_type 是 'upload'|'tts'|'material' / 'upload'|'source'|'material'；status 是 6 态）
- `backend/app/schemas/video_gen.py` — `VideoGenCreateRequest` / `VideoGenTaskResponse` / `VideoGenListResponse` / `VideoGenHealthResponse` / `VideoGenSaveToMaterialRequest` / `VideoGenSaveToMaterialResponse`
- `backend/app/services/video_gen_service.py` — httpx 客户端单例 + 3+3 源解析 + `create_task` + `_submit_and_poll` 后台 daemon thread + `_download_result` 流式落盘 + `cancel_task` + `resume_running_tasks`（标 interrupted）+ `save_to_material_library`
- `backend/app/api/video_gen.py` — 7 个端点

**修改**：
- `backend/main.py` — 注册 `video_gen_router` + startup 调 `resume_video_gen_tasks(settings)`
- `backend/app/config.py` — 加 4 字段：`heygem_base_url` / `heygem_enabled` / `heygem_request_timeout` / `video_gen_vram_strategy`；`get_settings()` env 解析
- `backend/.env.example` — 同步 4 个新 env vars
- `backend/app/models/database.py::init_db` — import `VideoGenTask`（让 `Base.metadata.create_all` 建表）
- `backend/app/utils/logger.py` — `_VIDEO_GEN_KEYS = ("video_service", "video_gen_service", "app.api.video_gen")` 把新日志合流到 `video_gen_*.log`
- `backend/app/utils/file_utils.py::ensure_data_layout` — 自动创建 `data/video_gen/`、`data/uploads/video_gen/{audio,video}/`
- `backend/requirements.txt` — 显式声明 `httpx>=0.27.0,<1.0`（openai SDK 实际已 transitive 引入，加入便于审计）

### C. master 前端

**新文件**：
- `frontend/src/api/videoGen.js` — `getVideoGenHealth / createVideoGenTask / listVideoGenTasks / getVideoGenTask / cancelVideoGenTask / getVideoGenDownloadUrl / saveVideoGenToMaterial`
- `frontend/src/store/modules/videoGen.js` — Pinia store（health 轮询引用计数 5s；任务轮询 2s 终态自动停；VRAM 策略 localStorage `vmis_video_gen_vram_strategy`）
- `frontend/src/components/videoGen/VideoGenStatusBar.vue` — 状态条（绿/红/灰三态 + GPU 信息）
- `frontend/src/components/videoGen/AudioSourcePicker.vue` — 3 tabs（upload / TTS 历史 / 素材库 audio），每个 tab 都通过 `update:selection` emit 出 `{type, file, ref}`
- `frontend/src/components/videoGen/VideoSourcePicker.vue` — 3 tabs（upload / source_videos / 素材库 video）
- `frontend/src/components/videoGen/SaveVideoToMaterialDialog.vue` — 保存到素材库对话框（display_name / library_kind 三选）

**修改**：
- `frontend/src/views/VideoGen.vue` — 从 31 行占位页重写为 ~250 行完整页（顶部状态条 + 三列布局 + 任务进度卡 + 近期任务表）
- `frontend/src/views/Settings.vue` — 在「TTS 模型管理」与下载弹窗之间插入「视频生成 / heygem 数字人 sidecar」section（连接状态 + VRAM 策略下拉 + 启动提示）

### D. 启动脚本

- `scripts/start_all.bat` — 解析 `--with-heygem`；带开关时多开一个 "heygem" cmd 窗执行 `vendor\heygem\start_api.bat`
- `scripts/start_all.sh` — 对称改

### E. submodule 引入

- 源 heygem repo (`D:/workspace/bzybox/v-project/heygem_win_no_docker_50_v2`)：`git init` + 初次 commit `4aaa648` + 加 sidecar commit `2674093`
- master `.gitmodules` 新增 `vendor/heygem` 条目，url=`file:///D:/...`
- master `.gitignore` 加 vendor/heygem 运行时目录双保险
- submodule 操作需 `-c protocol.file.allow=always`（Git 2.38+ CVE-2022-39253 默认拒绝 file://）

### F. 文档

- `CLAUDE.md`
  - 第 7 条更新表述（"视频生成本期仍为占位页" → "Phase-1 已上线"）
  - 新增第 9 条「视频生成 (Video Gen)」
  - Common Change Patterns 新增「Change Video Gen behavior」
- 本 changelog
- 计划文档 [`docs/20260517_0307_video_gen_phase1_plan.md`](20260517_0307_video_gen_phase1_plan.md)

---

## 用户操作步骤（验收前必做）

1. **首次启用 heygem**（仅一次）：
   ```
   cd vendor\heygem
   py39\python.exe -m pip install fastapi "uvicorn[standard]" python-multipart
   ```
   （`start_api.bat` 启动时也会自检并自动 pip，但若有代理建议手动一次。）

2. **重启 backend**（FastAPI 加了新路由 / 新 model 表 / 新配置；按你协作规则我未代起）：
   ```
   scripts\start_all.bat --with-heygem
   ```

3. **打开** http://localhost:5173/video-gen，等顶部状态条变绿（首次约 30s heygem 初始化）。

## 验收清单（请按场景跑）

| # | 场景 | 预期 |
|---|---|---|
| 1 | 仅启 backend + frontend，不起 heygem | `/video-gen` 顶部红色状态条 + 提交按钮 disabled |
| 2 | `start_all.bat --with-heygem` | 3 个 cmd 窗（backend / frontend / heygem），30s 内状态条变绿 |
| 3 | 上传 wav + 上传 mp4 → 提交 | `data/video_gen/{id}.mp4` 生成 + 页面预览能播 |
| 4 | 从 TTS 历史选音频 + 从 source_videos 选视频 → 提交 | 同 #3 |
| 5 | 任务运行中刷新页面 | 进度条恢复（轮询续上） |
| 6 | 后端重启 | 未完任务 → `interrupted`，列表可见 |
| 7 | 完成后点「保存到素材库」 | materials 列表出现新条目，type=video |
| 8 | 日志查看器「视频生成」tab | 全过程日志可见（httpx 请求/响应 + heygem phase 切换） |
| 9 | Settings 切 VRAM 策略 | 保存成功 toast；Phase-1 不生效但 localStorage 已写 |

---

## 未实装（Phase-2 候选）

- 自动显存调度：tts_unload（heygem 任务提交前主动调 `tts_service.unload_all`）+ cuda_isolate（双卡分离）
- 中断任务的自动续跑（当前 Phase-1 重启即 interrupted）
- 上传大文件本地路径传递（避免 multipart 长上传）
- 多用户队列 / 并发限流
- 数字人 mp4 自动回灌 master「任务」流（端到端流水线）
- VideoGen i18n（沿用 zh-CN inline 文案；后续与 TTS / CopyGen 对齐 bilingual key 结构）

---

## 关键风险与缓解

| 风险 | 缓解 |
|---|---|
| heygem 便携 py39 装 fastapi 失败（代理 / 防火墙） | `start_api.bat` 自检并提示；用户手动跑 pip 命令 |
| heygem 单卡 + TTS 同时跑 OOM | Phase-1 交用户判断；Settings dropdown 已埋 Phase-2 自动卸载位 |
| heygem submodule 远端是 file:// | 单机 OK；多机协作需后续推到真远端（建议私有 Gitea/GitHub） |
| heygem 长任务 + master 重启 | Phase-1 不续跑，标 interrupted；用户重新提交 |
| 大 reference video multipart 上传慢 | Phase-1 接受；Phase-2 改本地路径直传 |

---

## Commit 待办（用户触发）

按你的协作规则 commit 由你决定时机。建议两步：

**Step 1 — heygem 子仓库已自动 commit（2 个 SHA）**
- `4aaa648` vendor heygem v2 portable (initial commit for master submodule)
- `2674093` feat: add FastAPI REST sidecar (api_server.py + start_api.bat) for master integration

**Step 2 — master 工作区改动**（你方便时一次性 commit）：
- `vendor/heygem` gitlink 指向新 SHA
- `.gitmodules` 新增 submodule 条目
- master 根 `.gitignore` 双保险条目
- backend/frontend/scripts/docs 全部 Phase-1 改动

