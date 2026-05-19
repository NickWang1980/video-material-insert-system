# 日志查看器扩展：文案生成 / 语音生成 / 视频生成 — 变更记录

- 时间：2026-05-15 23:02
- 分支：feature/3.0-adding-tts-module
- 触发：在「日志」模块中为 文案生成 / TTS / 视频生成 三个上游模块新增独立日志类别；文案生成必须含 prompt request body / response payload body / token consumed。

## 背景与现状

变更前日志查看器 4 类：`asr` / `task`（FFmpeg）/ `app`（系统）/ `rough_cut`（混剪），与新的"视频生产"分组（文案 / 语音 / 视频）不对应。
- TTS / 视频工具（video_service）的日志全部混进 `app_*.log`，找定位困难。
- `copy_gen` 全部用 Python stdlib `logging.getLogger(__name__)`，**不会**被 loguru 文件 sink 抓到 → 之前的 prompt / response 调用根本未落盘。

## 改动总览

### 1. `backend/app/utils/logger.py` — 桥接 + 4 sinks

- 新增 `_InterceptHandler`：把 Python stdlib `logging` 的 LogRecord 路由进 loguru（保留真实调用栈深度），用于让 `copy_gen` / `openai` SDK 日志进入文件 sink。
- 新增 4 个 loguru 文件 sink，按模块归档（10MB 轮转、UTF-8、按时间戳命名）：
  - `tts_{time}.log` — filter: `tts_service` 或 `app.api.tts` in `record["name"]`
  - `copy_gen_{time}.log` — filter: `copy_gen` in name
  - `video_gen_{time}.log` — filter: `video_service` in name
  - `app_{time}.log` — filter: 以上 4 类之外的全部模块（已重写 filter，不再重复收）
- `asr_{time}.log` 保持原状（独占 ASR）。
- 桥接安装幂等：可重复调用，不叠加 handler。
- 清空 `uvicorn`/`fastapi`/`openai` 等 stdlib logger 自带 handler，避免双写。

### 2. `backend/app/services/log_viewer_service.py` — 新增 3 个类别

```
copy_gen   → 文案生成 → copy_gen_*.log
tts        → 语音生成 → tts_*.log
video_gen  → 视频生成 → video_gen_*.log
```

显示顺序：文案 → 语音 → 视频 → ASR → 任务 → 系统 → 混剪。前端 `LogsViewer.vue` 无需改动（tab 由后端 categories 数据驱动）。

### 3. `backend/app/services/copy_gen/llm_client.py` — 详细日志

`chat_completion()` 新增：
- 调用前打印**完整 request body**：`{"model", "temperature", "max_tokens", "messages": [...]}`（不含 api_key — client 已携带，避免泄露）。
- 用 `time.perf_counter()` 测量本次调用耗时。
- 调用后打印 `usage`（prompt_tokens / completion_tokens / total_tokens）+ elapsed 秒数。
- 打印**完整 response body**：`id / model / created / object / choices[*] / usage`（用 `_safe_dump` 截断到 100 KB/字段防爆）。
- 任何异常路径都会先 `logger.exception` 留底，再向上抛。

### 4. `backend/app/services/copy_gen/generator_service.py` — 上下文日志

`_run_generation()` 新增：
- 请求参数摘要（topic / platform / template / target±tolerance / versions / agent / model_config_id）。
- 完整 `user_prompt` 落盘（多版本共用）。
- `agent_system_prompt` / `model_system_prompt`（若存在）。
- 每版结束后打印解析结果（lines / plain_chars / qwen3_chars）。
- 落库完成后打印 `generation_id / total_elapsed / versions`，便于按生成 ID 回查日志。

### 5. `backend/app/api/tts.py` — 关键端点日志

之前没有 logger。新增：
- `/load` / `/load-custom` / `/unload` 触发与结果。
- `/synthesize` 请求摘要（text_len / language / voice / emotion / speed / ref_audio? / target_model）、503 拒绝、400 错误、500 异常、成功（audio URL + duration）。

### 6. `backend/app/services/video_service.py` — 关键路径日志

之前仅 1 处。新增 `[video_gen]` 前缀的：
- `probe_video` 开始 + 成功（尺寸 / 时长 / 是否有音轨）。
- `export_audio_track` 开始 / 成功 / 失败。
- `strip_video_audio` 开始、stream-copy 成功 / 失败回退、re-encode 成功 / 失败。
- `run_ffmpeg` 完整命令、非零退出码、成功收尾。

## 是否需要其他操作

| 项目             | 是否需要 | 说明 |
| ---------------- | -------- | ---- |
| 重启后端 uvicorn | ✅ 需要 | `configure_logging` 在启动钩子里只调一次；需重启进程才会生效，新日志文件会按 `{time:YYYYMMDD_HHmmss}.log` 重新创建。 |
| 重新 build 前端  | ❌ 不需要 | 类别由 `/api/logs/categories` 动态返回，`LogsViewer.vue` 自动渲染新 tab。 |
| 数据库迁移       | ❌ 不需要 | 未改 schema。 |
| 重装依赖         | ❌ 不需要 | 仅使用既有的 loguru / stdlib logging。 |

## 安全 / 隐私

- 日志中**不含** `api_key`：`request_log` 中只暴露 `model / temperature / max_tokens / messages`；`base_url` 也未写入（client 携带）。
- `_safe_dump` 单字段截断至 100 KB，超出会追加 `... (truncated, total N chars)`。极长 prompt 不会撑爆磁盘。
- 文件 sink rotate=10 MB，老文件自动归档。

## 验证步骤（建议手动）

```text
1. 重启后端：scripts/start_all.bat（或 uvicorn backend.main:app --reload --port 8000）
2. 触发：
   - /copy-gen 页面 → 任选模板 → 生成一次
   - /tts 页面     → 输入文本 → 合成一次
   - /tasks 或 /rough-cut → 跑一次能触发 FFmpeg 的任务
3. 打开 /logs（日志查看器）
4. 检查左上 tab：「文案生成」「语音生成」「视频生成」三类已出现，各自有刚生成的 *.log
5. 点开「文案生成」最新一条 → 应看到：
   - "[copy_gen] request topic=..." 摘要
   - "[copy_gen] user_prompt=..." 全文
   - "[copy_gen][llm] request_body={...messages...}"
   - "[copy_gen][llm] usage prompt=... completion=... total=..."
   - "[copy_gen][llm] response_body={...choices...usage...}"
```

## 受影响文件

- 修改：`backend/app/utils/logger.py`
- 修改：`backend/app/services/log_viewer_service.py`
- 修改：`backend/app/services/copy_gen/llm_client.py`
- 修改：`backend/app/services/copy_gen/generator_service.py`
- 修改：`backend/app/api/tts.py`
- 修改：`backend/app/services/video_service.py`
- 修改：`CLAUDE.md`（同步"日志"小节）
- 新增：`docs/20260515_2302_logs_module_expansion_changelog.md`

## Token 估算

- input（读）：约 19,000 tokens（CLAUDE.md、logger.py、log_viewer_service.py、LogsViewer.vue、copy_gen 全套、tts_service / api、video_service 等）
- output（写）：约 4,200 tokens（logger.py 全量重写、log_viewer_service edit、copy_gen / tts / video 增量 edit、本 changelog）
