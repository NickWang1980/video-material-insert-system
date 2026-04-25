# API接口文档（摘要）

基础说明：
- Base URL：`/api`
- 上传接口使用：`multipart/form-data`

---

## 混剪工作台 Rough Cut

### `GET /api/rough-cut/projects`
获取混剪项目列表。

### `POST /api/rough-cut/projects`
创建混剪项目。
- 请求体：`{ title, script, scriptFileName? }`
- 当 `scriptFileName` 存在时，后端按“严格角色剧本”处理：剧本必须包含 `A:`、`B：`、`C（说明）：` 这类角色前缀，否则返回 `400`。
- 创建成功后会立即初始化：
  - 动态角色列表 `roles`
  - 分镜头句子 `sentences`
  - 列表摘要 `roleCount / assetCount / stageSummary`

### `PATCH /api/rough-cut/projects/{project_id}`
更新混剪项目。
- 请求体：`{ title?, script?, scriptFileName? }`
- 支持：
  - 项目重命名
  - 替换剧本 TXT 内容
  - 更新剧本原始文件名
- 替换剧本时会重建 `roles/sentences`，并清空旧 `timeline/preview/output`。

### `GET /api/rough-cut/projects/{project_id}`
获取混剪项目详情（句子、角色、素材、时间线、日志、预览/导出URL）。
- 返回扩展字段：
  - `scriptFileName`
  - `roleCount`
  - `assetCount`
  - `stageSummary`

### `DELETE /api/rough-cut/projects/{project_id}`
删除混剪项目。
- 行为：删除项目记录，并清理该项目素材、ASR字幕、预览文件、导出文件与项目上传目录。

### `POST /api/rough-cut/projects/{project_id}/assets`
上传角色素材。
- 表单字段：`role_id`, `files[]`
- 规则：同一 `role_id` 支持多素材追加上传（不替换旧素材）。
- 行为：每个素材上传后自动触发独立 ASR 识别（简体中文）。

### `GET /api/rough-cut/projects/{project_id}/assets`
获取当前项目的角色素材列表。
- 资产扩展字段：`asrStatus`, `asrProgress`, `asrError`, `asrSrtPath`, `matchedChars`, `srtTotalChars`, `unmatchedChars`, `matchPercent`, `errorPercent`, `gatePassed`。
- 匹配率定义：`matchPercent = matchedChars / srtTotalChars * 100`，`errorPercent = unmatchedChars / srtTotalChars * 100`。

### `GET /api/rough-cut/projects/{project_id}/compare`
获取混剪项目的“主文本 vs 角色ASR文本”对比数据（项目/角色/素材三级分页弹窗使用）。
- 角色层新增：`roleSummary`
- 素材层新增：`assets[]`（每个素材独立的文本、匹配统计、`manualGatePassed` 与ASR状态）

### `PATCH /api/rough-cut/projects/{project_id}/assets/{asset_id}/manual-gate`
设置素材手动通过状态。
- 请求体：`{ manualPassed: boolean }`
- 用途：在匹配对比页面对单素材手动放行/取消放行。

### `DELETE /api/rough-cut/projects/{project_id}/assets/{asset_id}`
删除素材（同时清空混剪时间线缓存，等待重新生成）。

### `GET /api/rough-cut/projects/{project_id}/assets/{asset_id}/media`
预览/下载指定角色素材原文件。

### `POST /api/rough-cut/projects/{project_id}/split-script`
拆句。
- 请求体：`{ script?: string }`

### `POST /api/rough-cut/projects/{project_id}/assign-roles`
分配角色。
- 请求体：`{ strategy, manualSequence?, primaryRoleId }`
- strategy：`auto | primary-first | manual-sequence`

### `PUT /api/rough-cut/projects/{project_id}/settings`
更新渲染参数。
- 请求体：`{ settings }`
- settings：
  - `aspectRatio`: `9:16 | 16:9 | 1:1`
  - `resolution`: `720p | 1080p`
  - `fps`: `25 | 30`
  - `audioMode`: `keep | mute | tts`
  - `subtitleMode`: `off | srt | burn`
  - `transitionMode`: `none | fade`
  - `roleStrategy`: `auto | primary-first | manual-sequence`
  - `manualSequence?`: 例如 `A+B+A+C+A`
  - `primaryRoleId`

### `POST /api/rough-cut/projects/{project_id}/build-timeline`
生成时间线。
- 请求体：`{ recalculateDurations: boolean }`

### `PATCH /api/rough-cut/projects/{project_id}/sentences/{sentence_id}`
更新单句配置。
- 请求体：`{ roleId?, estimatedDuration?, locked? }`

### `POST /api/rough-cut/projects/{project_id}/regenerate-sentence/{sentence_id}`
仅重生某一句对应片段。

### `POST /api/rough-cut/projects/{project_id}/export`
导出任务（异步）。
- 请求体：`{ mode: "preview" | "final" }`
- 约束：若角色素材匹配率门槛未达 `80%` 且未手动通过，接口返回 `400`。

### `GET /api/rough-cut/projects/{project_id}/status`
获取混剪导出状态。
- 扩展字段：`pipelineProgress`, `rolesAsrProgress[]`, `roughCutEnabled`, `roughCutEnabledReason`。

### `GET /api/rough-cut/projects/{project_id}/media?type=preview|output`
下载/播放混剪媒体文件。

### 自动预览调度
- 角色素材上传并完成 ASR 后，后端会自动重算 gate。
- 当剧本中的全部角色都已有素材，且这些角色下全部素材都已 `completed` 且 `gatePassed` / `manualGatePassed` 时，后端会自动串行执行：
  - `assign_roles`
  - `build_timeline`
  - `export(mode=preview)`

---

## 任务 Tasks
- `POST /api/tasks/keyword-collision-check`
- `POST /api/tasks`
- `GET /api/tasks`
- `GET /api/tasks/{id}`
- `POST /api/tasks/{id}/retry`
- `POST /api/tasks/{id}/stop`
- `DELETE /api/tasks/{id}`
- `GET /api/tasks/{id}/output`
- `GET /api/tasks/{id}/report`
- `GET /api/tasks/{id}/log`
- `GET /api/tasks/{id}/log/text`

## 源视频库 Source Videos
- `POST /api/source-videos`
- `GET /api/source-videos`
- `PUT /api/source-videos/{id}`
- `DELETE /api/source-videos/{id}`
- `POST /api/source-videos/{id}/asr/retry`
- `GET /api/source-videos/{id}/audio?format=wav|flac`
- `GET /api/source-videos/{id}/subtitle?source=uploaded|asr`
- `GET /api/source-videos/{id}/subtitle/parsed?source=uploaded|asr`

## 配置模板 Config Templates
- `POST /api/config-templates`
- `GET /api/config-templates`
- `GET /api/config-templates/{id}`
- `PUT /api/config-templates/{id}`
- `DELETE /api/config-templates/{id}`
- `POST /api/config-templates/import`
- `GET /api/config-templates/{id}/export`

## 素材库 Materials
- `GET /api/materials/tree`
- `POST /api/materials/products`
- `PUT /api/materials/products/{id}`
- `DELETE /api/materials/products/{id}`
- `POST /api/materials/products/{id}/scripts`
- `PUT /api/materials/scripts/{id}`
- `DELETE /api/materials/scripts/{id}`
- `POST /api/materials`
- `GET /api/materials`
- `GET /api/materials/{id}/preview`
- `PUT /api/materials/{id}`
- `DELETE /api/materials/{id}`
- `POST /api/materials/{id}/file`
- `DELETE /api/materials/{id}/folders/{script_folder_id}`

## 系统设置 Settings
- `GET /api/settings`
- `PUT /api/settings`

## 统计 Stats
- `GET /api/stats`
