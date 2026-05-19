# 视频生成模块 Phase-1 集成 heygem 计划

- 创建时间：2026-05-17 03:07
- 作者：Claude（在 Nicholas 指导下）
- 目标分支：`feature/3.0-adding-tts-module`
- 关联占位页：`frontend/src/views/VideoGen.vue` / 路由 `/video-gen`
- 关联上游模块：heygem 数字人推理引擎（`D:/workspace/bzybox/v-project/heygem_win_no_docker_50_v2`）

---

## 0. 决策记录（来自 2026-05-17 用户对齐）

| 议题 | 决策 | 备注 |
|---|---|---|
| **集成形态** | 独立 sidecar（HTTP REST），master 通过 `httpx` 调用 | heygem 含 `.pyc`-only 模块 + 13 GB 便携 py39，**不可** vendoring 进 master venv |
| **heygem 物理位置** | **纳入 master 仓库的 git submodule** | 见下方 §3.0 "submodule 引入步骤"，需先解决 heygem 本身的 git 远端 |
| **GPU/显存策略** | **默认：用户手动决定** —— 不做自动调度；前端给开关；**Settings 页面提供策略下拉**：①手动 ②TTS 主动 unload ③CUDA_VISIBLE_DEVICES 隔离（备用） | Phase-1 只实装策略①与开关；②/③ 留接口位 |
| **音频输入源** | 上传 .wav + 从 TTS 历史 + 从素材库 | 三源全接 |
| **参考视频输入源** | 默认按音频同等覆盖：上传 .mp4 + 从 `source_videos` 选 + 从素材库 video 类选 | 用户未明确，按对称推论；不同意可调 |
| **下一步** | 先出本计划 md，再实装 | |

---

## 1. Phase-1 目标 / 范围（What & What-NOT）

### 必须交付
1. heygem 端能以 REST 服务方式启动（不再依赖 Gradio UI 打开浏览器即可消费）。
2. master 后端 `/api/video-gen/*` 一组 REST 接口：create / list / detail / cancel / download。
3. master 后端任务模型 `VideoGenTask` 落库，支持服务重启后状态恢复（参考 `tasks` 模块）。
4. 前端 `/video-gen` 占位页改为真实页面：三源音频选择 + 三源参考视频选择 + 提交 + 进度 + 预览 + "保存到素材库"。
5. `scripts/start_all.bat` / `.sh` 新增 `--with-heygem` 开关，可一键起 heygem 服务（在新 cmd 窗口）。
6. 显存调度策略设置项落地（Phase-1 只实装"手动"+ Settings 下拉占位）。
7. 日志归档到现有 `video_gen_*.log`（`logger._VIDEO_GEN_KEYS` 增加 `video_gen_service`）。
8. CLAUDE.md 更新（新章节 "9. 视频生成 (Video Gen)" + Common Change Patterns）。
9. `docs/20260517_0307_video_gen_phase1_changelog.md` 在收尾时写入实施汇总。

### 明确 **不在** Phase-1
- 自动显存调度（TTS unload / CUDA 隔离）—— 仅留接口，不实装。
- 串行队列 / 多任务并发限流（heygem 自身已串行，简单先调先服）。
- 数字人 mp4 自动回灌 master「任务」流（端到端）。
- 多形象库 / 演员管理。
- heygem 升级版本管理 / 健康自愈。

---

## 2. 架构图（Phase-1）

```
┌─────────────────────────────────────────────────────────────┐
│                    master 项目（本仓库）                       │
│                                                              │
│  Vue (/video-gen) ─── /api/video-gen/* ─── video_gen_service │
│                                                  │           │
│                                                  ▼  httpx    │
└──────────────────────────────────────────────────┬───────────┘
                                                   │
                            ┌──────────────────────▼───────────────────┐
                            │ heygem (git submodule) :8383              │
                            │   api_server.py (FastAPI)                 │
                            │     ├─ POST /synthesize  → 返回 work_id   │
                            │     ├─ GET  /status/{id} → 阶段+百分比     │
                            │     └─ GET  /result/{id} → mp4 流式       │
                            │   内部沿用现有 VideoProcessor               │
                            └────────────────────────────────────────────┘
```

---

## 3. 任务拆解（按文件 + 进度 %）

### 3.0 准备：heygem submodule 引入（10%）

⬜ **步骤 0.1** 把 heygem 本机目录 init 成 git 仓库（若未有），并推到远端（建议自建 Gitea 私库或 GitHub 私仓）
- 命令草稿（**用户执行**，我不代跑）：
  ```
  cd D:/workspace/bzybox/v-project/heygem_win_no_docker_50_v2
  git init && git add -A && git commit -m "vendor heygem v2 portable"
  git remote add origin <your-private-repo-url>
  git push -u origin master
  ```
- `.gitignore` 至少包含：`py39/`、`tmp/`、`result/`、`audio/`、`data/temp/`、`data/log/`、`hf_download/`、`tf_download/`（避免推送 13 GB 便携 env 与中间产物）。

⬜ **步骤 0.2** master 仓库添加 submodule
- 路径：`vendor/heygem`（新建 `vendor/` 目录用于第三方）
- 命令草稿（**用户执行**）：
  ```
  git submodule add <heygem-repo-url> vendor/heygem
  git submodule update --init --recursive
  ```
- 团队拉新后只需 `git submodule update --init`。

⬜ **步骤 0.3** 在 master 根目录 `.gitignore` 加 `vendor/heygem/py39/` 等运行时目录的过滤（双重保险）。

> ⚠️ **若用户暂无 git 远端**：退化方案——`vendor/heygem` 作为普通目录复制进来 + 写入 `.gitignore`，等远端就绪后再切换到 submodule。

---

### 3.1 heygem 侧改造（20%）

⬜ **新建** `vendor/heygem/api_server.py`（约 200 行 FastAPI）
- `POST /api/heygem/synthesize` (multipart: `audio_file`, `video_file`) → `{work_id: str}`，立即返回，后台线程跑 `VideoProcessor.process_video`
- `GET /api/heygem/status/{work_id}` → `{phase, percent, message, completed, success, error}`
- `GET /api/heygem/result/{work_id}` → FileResponse 返回 mp4（仅在 completed=True 时）
- `GET /api/heygem/health` → `{ready: bool, gpu: str, version: "v2"}`
- 内部用一份全局 `dict[work_id -> task_state]`，状态机参考现有 `VideoProcessor.process_video` 的 6 步 yield 拆出 phase
- 复用现有 `VideoProcessor` 单例，避免每次重新加载 ~750 MB 权重

⬜ **新建** `vendor/heygem/start_api.bat`（复刻 `一键运行.bat` 的所有环境变量设置，仅最后一行改为 `uvicorn api_server:app --host 0.0.0.0 --port 8383`）
- 端口与现有 `config.ini` 的 `[http_server] server_port = 8383` 保持一致。
- 在便携 py39 中安装 fastapi / uvicorn（仅一次）：`py39\python.exe -m pip install fastapi uvicorn[standard] python-multipart`

⬜ **保留** 原 `app.py` / `一键运行.bat` 不动（用户可选择老 Gradio 模式或新 API 模式）。

---

### 3.2 master 后端（35%）

⬜ **新模型** `backend/app/models/video_gen.py` —— `VideoGenTask`
- 字段：`id`(uuid) / `audio_source_type`(upload/tts/material) / `audio_source_ref` / `audio_path` / `video_source_type` / `video_source_ref` / `video_path` / `heygem_work_id` / `status`(pending/running/succeeded/failed/cancelled) / `phase` / `progress` / `result_path` / `error_message` / `created_at` / `updated_at`
- 注册到 `backend/app/models/database.py::_ensure_schema_compatibility()`，**新增表用 `CREATE TABLE IF NOT EXISTS`，不破坏现有库**。

⬜ **新 Pydantic** `backend/app/schemas/video_gen.py`
- `VideoGenCreateRequest` / `VideoGenTaskResponse` / `VideoGenStatusResponse` / `VideoGenListResponse`

⬜ **新服务** `backend/app/services/video_gen_service.py`
- 内部 httpx Client（lazy 单例）指向 `settings.heygem_base_url`
- `create_task(req)`：解析三种音频源 → 落地 wav 临时文件；解析三种视频源 → mp4 临时文件；调 heygem `/synthesize` 拿 `work_id`；落库；启动后台线程轮询
- `_poll_loop(task_id)`：每 3 秒拉 heygem `/status`，更新 `phase/progress`；终态时下载 `/result` 到 `data/video_gen/{task_id}.mp4`，写 `result_path`、置 `status=succeeded`
- `resume_running_tasks(settings)`：在 main.py startup 调用，恢复服务重启前未完成的任务
- 全部日志用 `logger.bind(name="video_gen_service")`，落 `video_gen_*.log`

⬜ **新路由** `backend/app/api/video_gen.py`
- `POST /api/video-gen` 创建任务（multipart：audio_file 可选 / video_file 可选 / json metadata 描述三源）
- `GET  /api/video-gen` 列表（分页）
- `GET  /api/video-gen/{id}` 详情
- `POST /api/video-gen/{id}/cancel` 取消
- `GET  /api/video-gen/{id}/download` 下载结果 mp4
- `POST /api/video-gen/{id}/save-to-material` 把结果作为 video 类型素材入库（调 `materials_service`）
- `GET  /api/video-gen/health` 透传 heygem `/health`

⬜ **接入** `backend/main.py`：
- `app.include_router(video_gen_router)`
- 启动钩子调 `video_gen_service.resume_running_tasks(settings)`

⬜ **配置** `backend/app/config.py` 增加：
- `heygem_base_url: str = "http://127.0.0.1:8383"`
- `heygem_enabled: bool = True`
- `heygem_request_timeout: int = 600`（heygem 任务长，需大超时）
- `video_gen_vram_strategy: str = "manual"`（manual / tts_unload / cuda_isolate；Phase-1 只生效 manual）

⬜ **配置示例** `backend/.env.example` 同步追加上述四项。

⬜ **日志** `backend/app/utils/logger.py`：
- `_VIDEO_GEN_KEYS = ("video_service", "video_gen_service")` —— 把新服务的日志合流到现有 `video_gen_*.log`
- 同步 `log_viewer_service._FILE_CATEGORIES` 无需变更（仍走 `video_gen_*.log` glob）

⬜ **数据目录** `backend/app/utils/file_utils.py::ensure_data_layout` 增加 `video_gen/` 子目录创建。

---

### 3.3 master 前端（30%）

⬜ **新 API wrapper** `frontend/src/api/videoGen.js` —— `createTask / getTask / listTasks / cancelTask / downloadUrl / saveToMaterial / getHealth`

⬜ **新 store** `frontend/src/store/modules/videoGen.js`（Pinia）
- 任务列表 + 当前任务状态轮询（2s）

⬜ **重写** `frontend/src/views/VideoGen.vue`（完整页面，约 350 行）
- 顶部：heygem 服务状态条（参考 TTS 模型状态栏样式：未连接时提示"请运行 vendor/heygem/start_api.bat 或在 Settings 中启用"）
- 左侧：**音频源 tabs**
  - Tab 1 上传：`el-upload` accept=".wav,.mp3"（mp3 由后端 convert_audio_to_16k）
  - Tab 2 TTS 历史：从 localStorage `vmis_tts_history` 读出近 50 条，列表选择，可试听
  - Tab 3 素材库：弹出 dialog 复用 `MaterialPickerDialog`（如未有则新建简化版，仅显示 audio 类型）
- 中间：**参考视频源 tabs**
  - Tab 1 上传：`el-upload` accept=".mp4,.mov"，上传后 ffprobe 提示"检测到 N 张人脸"（Phase-1 可省略人脸预检，仅显示分辨率/时长）
  - Tab 2 从原视频选：表格列出 `source_videos`
  - Tab 3 从素材库选：复用素材选择 dialog（filter video）
- 右侧：**任务卡片**
  - 提交按钮 → 显示 phase + progress 条 + 预估剩余时间
  - 完成 → `<video>` 预览 + 下载 + "保存到素材库" + "进入混剪"
  - 失败 → 错误详情 + 重试

⬜ **新组件** `frontend/src/components/videoGen/`
- `AudioSourcePicker.vue`
- `VideoSourcePicker.vue`
- `VideoGenStatusBar.vue`
- `SaveVideoToMaterialDialog.vue`

⬜ **Settings 页新增 section**「视频生成 / 显存策略」
- `frontend/src/views/Settings.vue` 增加：heygem base URL、heygem enabled 开关、VRAM 策略下拉（manual / tts_unload (Phase-2) / cuda_isolate (Phase-2)）
- 后端 `backend/app/api/settings.py` 暴露读写接口（持久化到数据库现有 system_config 表）

⬜ **i18n**（保持现网约定，TTS/CopyGen 都有 zh-CN/en-US）
- 新增 `frontend/src/locale/{zh-CN,en-US}/videoGen.json`
- 在 `frontend/src/main.js` 或 i18n 入口注册

---

### 3.4 启动脚本（3%）

⬜ `scripts/start_all.bat` 增加 `--with-heygem` 分支：
- 若带 `--with-heygem`：`start "heygem" cmd /k vendor\heygem\start_api.bat`
- 不带：跳过（保持兼容）

⬜ `scripts/start_all.sh` 对称修改。

---

### 3.5 文档（2%）

⬜ `CLAUDE.md` 新增第 9 条 "视频生成 (Video Gen)" 描述本模块；Common Change Patterns 增加 "Change Video Gen behavior" 段落。

⬜ **收尾时**写 changelog：`docs/20260517_<HHMM>_video_gen_phase1_changelog.md`

---

## 4. 验收标准（用户手动验收，我不代测）

| # | 场景 | 预期 |
|---|---|---|
| 1 | 仅启 master 后端 + 前端，不起 heygem | `/video-gen` 顶部红色提示"heygem 服务未连接"，提交按钮 disabled |
| 2 | `start_all.bat --with-heygem` 一键启 | 3 个 cmd 窗口：backend / frontend / heygem；30s 内 heygem 状态条变绿 |
| 3 | 上传 wav + 上传 reference mp4 → 提交 | 后端 `data/video_gen/{id}.mp4` 生成；前端预览能播；耗时约 `duration × 1.5 + 30s` |
| 4 | 从 TTS 历史选音频 + 从 source_videos 选视频 | 同 #3 |
| 5 | 任务过程中刷新页面 | 进度恢复显示（轮询自动续上） |
| 6 | 后端重启 | 未完成的任务状态置为 `interrupted`，列表可见 |
| 7 | 完成后点"保存到素材库" | `materials` 列表出现新条目，类型 video |
| 8 | 日志查看器 "视频生成" tab | 能看到本次合成全过程日志（含 httpx 请求/响应 + heygem 阶段切换） |
| 9 | Settings 改 VRAM 策略为 tts_unload | 保存成功；Phase-1 不生效但配置可见 |

---

## 5. 工时估算（一人开发）

| 阶段 | 估时 | 备注 |
|---|---|---|
| 3.0 submodule 引入 | 0.5h | 含 .gitignore 调整；推远端由用户做 |
| 3.1 heygem api_server | 2h | + py39 装 fastapi（首次） |
| 3.2 backend | 4h | model / service / api / 配置 / 日志 |
| 3.3 frontend | 5h | 3 个 picker + 状态条 + Settings + i18n |
| 3.4 启动脚本 | 0.5h | |
| 3.5 文档 | 0.5h | CLAUDE.md + changelog |
| 自测调试 | 2h | 真机端到端跑 1-2 次 |
| **合计** | **~14.5h** | 跨 2 个工作日 |

---

## 6. 风险 / 未决项

| 风险 | 缓解 |
|---|---|
| heygem 便携 py39 装 fastapi 失败（pip 受限于代理） | `start_api.bat` 启动前自检；失败提示用户手动跑安装命令 |
| `.pyc` 反编译模块对 Python 版本敏感 | 不动 py39 内任何文件；仅在外层包一个 api_server.py |
| heygem submodule 远端用户暂无 | §3.0 退化方案：先复制 + .gitignore，过渡 |
| heygem 长任务中 master 重启 | Phase-1 暂置 `interrupted` 不自动续跑；用户手动重提；Phase-2 再补"接管 in-flight work_id" |
| GPU OOM（TTS + heygem 同时跑） | 现在交给用户判断；Settings 页有策略下拉为后续埋点 |
| 上传大 mp4 (>500MB) 走 multipart 慢 | Phase-1 接受；Phase-2 改为本地路径传递（heygem 与 master 同机时） |
| 多用户并发 | Phase-1 共享一个 heygem 实例，先到先服；高级队列后置 |

---

## 7. 修改完成后用户需做

1. **重启 backend**（FastAPI 加了路由 / model 表 / 配置）。
2. **重启 frontend**（Vite 一般 HMR 已够，但路由级变更建议刷新）。
3. **首次启用 heygem**：去 `vendor/heygem` 跑一次 `py39\python.exe -m pip install fastapi uvicorn[standard] python-multipart`（仅一次）。
4. **跑一遍** §4 的 9 个验收场景。
5. **签收** changelog 后由我提交 commit（按你的协作规则，commit 由你触发）。

---

## 8. 自检清单（实施时维护）

- [ ] 3.0 heygem 推远端 + master 添加 submodule
- [ ] 3.1 heygem `api_server.py` + `start_api.bat`
- [ ] 3.2.1 backend model `VideoGenTask`
- [ ] 3.2.2 backend Pydantic schemas
- [ ] 3.2.3 backend `video_gen_service.py`
- [ ] 3.2.4 backend `api/video_gen.py`
- [ ] 3.2.5 backend `main.py` 注册路由 + startup 恢复
- [ ] 3.2.6 backend `config.py` + `.env.example`
- [ ] 3.2.7 backend `utils/logger.py` `_VIDEO_GEN_KEYS` 追加
- [ ] 3.2.8 backend `utils/file_utils.py` 数据目录
- [ ] 3.3.1 frontend `api/videoGen.js`
- [ ] 3.3.2 frontend `store/modules/videoGen.js`
- [ ] 3.3.3 frontend `views/VideoGen.vue`（重写）
- [ ] 3.3.4 frontend `components/videoGen/*`
- [ ] 3.3.5 frontend Settings 页 VRAM 策略 section
- [ ] 3.3.6 frontend i18n `locale/{zh,en}/videoGen.json`
- [ ] 3.4 `scripts/start_all.{bat,sh}` `--with-heygem`
- [ ] 3.5 CLAUDE.md 第 9 条 + Common Change Patterns
- [ ] 收尾 changelog
