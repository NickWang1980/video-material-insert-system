# API 接口文档（摘要）

基础说明：
- Base URL：`/api`
- 文件上传接口使用 `multipart/form-data`

---

## 任务 Tasks

### `POST /api/tasks`
创建任务（源视频条目 + 多模板）

表单字段：
- `task_name`：任务名称（必填）
- `source_entry_id`：源视频条目 ID（必填）
- `config_ids`：可多次传入（模板 ID 列表）
- `subtitle_source`：`uploaded|asr`（可选，默认 `uploaded`）
- `add_subtitle_to_video`：`true|false`（可选，默认 `false`）

规则：
- 多模板关键词冲突返回 `400`。
- `subtitle_source=asr` 时，按“ASR SRT 文件存在优先”校验；若文件不存在，再按 `asr_status` 反馈未就绪原因并返回 `400`。

### `GET /api/tasks`
任务列表（支持 `status` 过滤），响应含：
- `source_templates`
- `source_video`
- `subtitle_source`
- `add_subtitle_to_video`

### `GET /api/tasks/{id}`
任务详情（同上）。

### 任务控制与下载
- `POST /api/tasks/{id}/retry`
- `POST /api/tasks/{id}/stop`
- `DELETE /api/tasks/{id}`
- `GET /api/tasks/{id}/output`
- `GET /api/tasks/{id}/report`
- `GET /api/tasks/{id}/log`
- `GET /api/tasks/{id}/log/text?tail_kb=256`

---

## 源视频库 Source Videos

### `POST /api/source-videos`
创建源视频条目（上传 `video`，`subtitle(.srt)` 可选）：
- 保存视频与（可选）上传 SRT
- 同步导出 `wav` + `flac`
- 异步 ASR 生成第二份 SRT

响应新增字段：
- `audio_wav_path`, `audio_flac_path`
- `asr_srt_path`, `asr_status`, `asr_error`, `asr_model_used`
- `asr_retry_count`, `asr_retry_max`
- `subtitle_line_count_user`, `subtitle_line_count_asr`
- `has_wav`, `has_flac`, `has_uploaded_srt`, `has_asr_srt`

2026-04-21 规则更新：
- `subtitle(.srt)` 改为可选；仅 `video` 必填。
- 未上传 `SRT` 时，后端仍会创建条目并异步启动 ASR。
- ASR 输出字幕命名为 `<源视频条目名称>.srt`（按条目目录保存）。

### `GET /api/source-videos`
返回条目列表（包含上述状态字段）。
- 当检测到 `asr_srt_path` 文件存在时，响应层会将 `asr_status` 以 `completed` 返回，避免前端误判可用性。

### `POST /api/source-videos/{id}/asr/retry`
手动触发该源视频条目的 ASR 重试：
- 重置重试计数并立即重跑识别。
- 用于 `failed` 或需要重新识别的场景。

### `PUT /api/source-videos/{id}`
重命名条目。

### `DELETE /api/source-videos/{id}`
删除条目（被任务引用时返回 `400`）。

### `GET /api/source-videos/{id}/audio?format=wav|flac`
下载音轨。

### `GET /api/source-videos/{id}/subtitle?source=uploaded|asr`
下载字幕文件。

### `GET /api/source-videos/{id}/subtitle/parsed?source=uploaded|asr`
返回解析后的字幕行（用于“识别预览”）。

---

## 配置模板 Config Templates
- `POST /api/config-templates`
- `GET /api/config-templates`
- `GET /api/config-templates/{id}`
- `PUT /api/config-templates/{id}`
- `DELETE /api/config-templates/{id}`
- `POST /api/config-templates/import`
- `GET /api/config-templates/{id}/export`

---

## 素材库 Materials
- `POST /api/materials`
- `GET /api/materials?file_type=image|gif|video|audio`
- `GET /api/materials/{id}/preview`
- `PUT /api/materials/{id}`
- `DELETE /api/materials/{id}`

---

## 系统设置 Settings

### `GET /api/settings`
返回：
- `output_format`
- `resolution`
- `video_bitrate_kbps`
- `subtitle_encoding`
- `subtitle_time_offset_seconds`
- `asr_model`（`small|medium`）

### `PUT /api/settings`
更新上述字段。

---

## 统计 Stats
- `GET /api/stats`
