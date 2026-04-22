# API 接口文档（摘要）

基础说明：
- Base URL：`/api`
- 上传接口使用 `multipart/form-data`

---

## 任务 Tasks

### `POST /api/tasks/keyword-collision-check`
创建前预检“同一字幕行多关键词命中”风险，不创建任务。

请求体（JSON）：
- `source_entry_id`：源视频条目 ID（必填）
- `config_ids`：模板 ID 列表（必填，多选顺序会保留）
- `subtitle_source`：`uploaded|asr`（可选，默认 `uploaded`）

响应：
- `warnings[]`：
  - `subtitle_index`
  - `start`
  - `end`
  - `text`
  - `matched_keywords[]`
  - `winner_keyword`
  - `suppressed_keywords[]`

---

### `POST /api/tasks`
创建任务（源视频条目 + 多模板）。

表单字段：
- `task_name`：任务名称（必填）
- `source_entry_id`：源视频条目 ID（必填）
- `config_ids`：模板 ID（可多次传入）
- `subtitle_source`：`uploaded|asr`（可选，默认 `uploaded`）
- `add_subtitle_to_video`：`true|false`（可选，默认 `false`）
- `collision_priority_json`：冲突优先级 JSON（可选），格式示例：`{"5":["精准","抖音"]}`

规则：
- 多模板“同名关键词冲突”返回 `400` 并阻止创建。
- “同一字幕行近距离冲突”仅警告，不阻止创建；运行时按“长词优先”抑制短词。

响应新增字段：
- `keyword_collision_warnings[]`（结构同预检接口）

---

### `GET /api/tasks`
任务列表（支持 `status` 过滤）。

响应重点字段：
- `source_templates[]`
- `source_video`
- `subtitle_source`
- `add_subtitle_to_video`
- `keyword_collision_warnings[]`

### `GET /api/tasks/{id}`
任务详情（同上字段，含创建时冲突预警快照）。

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
- 同步导出 `wav + flac`
- 异步 ASR 生成第二份 SRT

响应字段包含：
- `audio_wav_path`, `audio_flac_path`
- `asr_srt_path`, `asr_status`, `asr_progress`, `asr_error`, `asr_model_used`
- `asr_retry_count`, `asr_retry_max`
- `subtitle_line_count_user`, `subtitle_line_count_asr`
- `video_duration_seconds`
- `has_wav`, `has_flac`, `has_uploaded_srt`, `has_asr_srt`

### `GET /api/source-videos`
返回条目列表。

可用性规则：
- 若 `asr_srt_path` 文件存在，返回中的 `asr_status` 以 `completed` 为准（状态自愈），避免前端误判。

### `POST /api/source-videos/{id}/asr/retry`
手动触发 ASR 重试。

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

### 产品分类素材库目录树重构（2026-04-22）
- `GET /api/materials/tree`：获取素材目录树（定量素材 + 产品目录 + 脚本子文件夹）
- `POST /api/materials/products`：新建产品目录
- `PUT /api/materials/products/{id}`：重命名产品目录
- `DELETE /api/materials/products/{id}`：删除产品目录（非空拒绝）
- `POST /api/materials/products/{id}/scripts`：新建脚本子文件夹
- `PUT /api/materials/scripts/{id}`：重命名脚本子文件夹
- `DELETE /api/materials/scripts/{id}`：删除脚本子文件夹（非空拒绝）
- `POST /api/materials` 上传参数调整：`library_kind + script_folder_id`（产品素材必填脚本子文件夹）
- `GET /api/materials` 新增筛选：`product_id`、`script_folder_id`
- 素材响应新增：`product_id/product_name/script_folder_id/script_folder_name`
- 模板CSV新增列：`素材库分类`、`产品目录`、`脚本子文件夹`

### 素材目录增强（未归档 + 多目录归档，2026-04-22）
- 上传：`POST /api/materials`
  - `library_kind`: `general|unfiled|product`
  - `script_folder_id`: 当 `library_kind=product` 必填
- 目录树：`GET /api/materials/tree` 返回 `general_label/unfiled_label/product_label/products[]`
- 归档：`POST /api/materials/{id}/file`
  - `target_type`: `general|unfiled|script`
  - `script_folder_id`: 当 `target_type=script` 必填
- 取消归档：`DELETE /api/materials/{id}/folders/{script_folder_id}`
- 素材列表：`GET /api/materials` 支持 `library_kind/product_id/script_folder_id` 过滤（`script_folder_id` 基于多对多归档关系）
- 素材响应新增：`folder_links[]`（素材被归档到的全部产品/子目录）
