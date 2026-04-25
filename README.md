# 短视频智能素材自动植入工具 V1.0

## 核心能力
- 任务管理：源视频条目 + 多模板合并 + 自动素材植入 + MP4/XLSX/TXT 下载。
- 源视频库：视频/SRT 绑定、可选 ASR 字幕、WAV/FLAC 音轨导出。
- 素材库：目录树管理、产品目录与子文件夹、多目录归档、预览与去音轨上传。
- 模板系统：关键词规则、5×5位置选择器、冲突层级设置、提示音配置。
- 新增功能：`/rough-cut/unit` 混剪单元（项目列表 + 剧本TXT上传 + 动态角色卡 + 自动ASR + 自动分镜头 + 自动预览混剪）。
- 新增功能：`/rough-cut/multi-role` 多角色混剪工作台（文案拆句 → 角色分配 → 时间线 → 预览/导出）。
  - 支持角色素材库管理：按项目独立、单角色多视频、批量上传、预览与删除。
  - 支持每个素材独立ASR识别（简体中文）与素材粒度匹配率门槛控制（全部素材 `>=80%` 或手动通过后可一键混剪）。
  - 支持ASR匹配对比弹窗：识别完成自动弹出，项目+角色+素材三级分页查看主文本与ASR文本对比，并支持“手动通过”。

## 目录结构
- `backend/`：FastAPI 后端（API + 服务层 + SQLite + FFmpeg/ASR）
- `frontend/`：Vue3 + Vite + Element Plus 前端
- `data/`：数据库、上传文件、输出文件
- `scripts/`：启动脚本
- `docs/`：接口与部署文档、变更记录

## 运行环境
- Python 3.11+
- Node.js 18+
- FFmpeg / ffprobe（系统可执行）

## 开发模式
```bash
./scripts/start_all.sh
```
或 Windows：
```bat
scripts\start_all.bat
```
- 前端：`http://localhost:5173`
- 后端：`http://localhost:8000`

## 生产模式（后端托管前端）
```bash
./scripts/start_all.sh --prod
```
或 Windows：
```bat
scripts\start_all.bat --prod
```
- 访问：`http://localhost:8000`

## 手动 CLI（编译 + 启动）
1. 安装后端依赖：`pip install -r backend/requirements.txt`
2. 安装前端依赖：`cd frontend && npm install`
3. 构建前端：`cd frontend && npm run build`
4. 启动后端：`python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000`

## 多角色混剪使用
1. 打开 `http://localhost:5173/rough-cut/multi-role`（生产态为 `http://localhost:8000/rough-cut/multi-role`）。
2. 输入文案，点击“自动拆句”。
3. 上传 A/B/C 角色素材（每个角色可上传多个，支持批量）。
4. 等待每个素材独立ASR识别并查看匹配率（`<80%` 强提示）。
5. 全部素材匹配率 `>=80%` 后“一键混剪”可点击；若单素材未达标，可在“匹配对比”弹窗中手动通过。
6. 生成时间线后，每句片段时长以匹配到的角色视频 ASR 片段真实长度为准，不限制 8 秒上限。

## 混剪单元使用
1. 打开 `http://localhost:5173/rough-cut/unit`（生产态为 `http://localhost:8000/rough-cut/unit`）。
2. 在顶部项目区新建混剪项目，并上传带角色前缀的 `.txt` 剧本。
3. 系统会按剧本自动识别角色并生成角色素材卡片。
4. 给每个角色拖拽/选择视频素材；上传后自动开始 ASR、自动计算匹配率。
5. 当剧本中的全部角色都已有素材，且这些角色下全部素材都已完成识别并达到门槛后，系统会自动生成分镜头、时间线和预览版混剪。
6. 如需人工干预，可在分镜头卡片打开“ASR匹配对比中心”，或修改句子时长后重新生成预览。

## 文档索引
- `docs/API接口文档.md`
- `docs/部署指南.md`
- `docs/项目开发文档.md`
- `docs/技术架构与技术栈.md`
