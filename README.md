# 短视频智能素材自动植入工具 V1.0

## 当前版本核心能力
- 源视频条目创建时自动导出音轨：`WAV + FLAC`。
- 支持用户上传 SRT，并支持后台 ASR 生成第二份 SRT（faster-whisper，本地离线）。
- 创建任务时可选择字幕来源：`uploaded`（默认）或 `asr`。
- 创建任务时可选“添加字幕SRT到视频”，默认不添加字幕到输出视频。
- 任务支持多模板合并、冲突拦截、下载成品/报告/日志、停止任务。
- 最近任务/任务列表支持显示任务耗费时间（`mm:ss`）。
- 素材库支持分类管理：`定量素材`、`未归档`、`产品分类素材（产品目录 + 子文件夹）`。
- 素材库已升级目录树：支持拖拽归档素材；同一素材可归档到多个脚本子文件夹。
- 模板规则支持目录上下文字段：`素材库分类`、`产品目录`、`脚本子文件夹`，同名素材可按目录精确绑定。

## 工程结构
- `backend/`：FastAPI 后端（API + 任务处理 + FFmpeg + ASR）
- `frontend/`：Vue3 + Vite + Element Plus + Tailwind
- `data/`：SQLite、上传文件、输出文件
- `scripts/`：启动与打包脚本
- `docs/`：项目说明文档

## 依赖与环境
- Python 3.11+
- Node.js 18+
- FFmpeg / ffprobe（需可在命令行直接调用）
- ASR 依赖：`faster-whisper`

## 开发模式启动
```bat
scripts\start_all.bat
```
或
```bash
./scripts/start_all.sh
```
- 前端：`http://localhost:5173`
- 后端：`http://localhost:8000`（OpenAPI：`/docs`）

## 生产模式启动
```bat
scripts\start_all.bat --prod
```
或
```bash
./scripts/start_all.sh --prod
```
- 访问：`http://localhost:8000/`

## 编译与启动 CLI（手动）
1. 安装后端依赖：`pip install -r backend/requirements.txt`
2. 安装前端依赖：`cd frontend && npm install`
3. 前端构建：`cd frontend && npm run build`
4. 开发启动：`python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload`
5. 生产启动（加载 `frontend/dist`）：`python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000`

## 关键业务规则（更新）
- ASR 为可选能力（本地离线），不依赖云 API。
- 默认字幕来源为用户上传 SRT；任务侧按“ASR SRT 文件存在优先”判断可用性。
- 源视频条目被任务引用时不可删除。
- 删除任务不会删除源视频条目文件（视频/SRT/音轨），仅删除任务产物。

## 文档索引
- `docs/项目开发文档.md`
- `docs/技术架构与技术栈.md`
- `docs/API接口文档.md`
- `docs/部署指南.md`

## 2026-04-21 更新（源视频条目）
- 新建源视频条目时，`SRT` 改为非必填。
- 未上传 `SRT` 时，前端会弹框提示将启动模型识别字幕（ASR）。
- ASR 字幕命名规则：`<源视频条目名称>.srt`（按条目独立目录保存）。
- 创建任务时：
  - 默认字幕来源仍为 `uploaded`；
  - 若条目未上传 `SRT`，仅当 `ASR` 完成后可选择 `ASR SRT` 创建任务。
- ASR 支持循环递推重试（默认最多 3 次），并支持手动“重试识别”。
- 修复 FFmpeg 大日志场景可能卡在 `75%` 的问题，新增超时保护与处理中心跳更新（75%→98%）。
