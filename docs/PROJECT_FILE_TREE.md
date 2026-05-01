# 项目文件清单

> 生成时间：2026-04-28
> 仅列出源代码、配置、文档与脚本，已排除依赖（`.venv` / `node_modules`）、缓存（`__pycache__` / `.pytest_cache`）、Git 元数据、运行时产物（`data/` / `frontend/dist/` / `dist/`）以及解压后的 ffmpeg 二进制目录。

## 项目根

- `.gitignore` (0.1 KB) — Git 忽略规则
- `CLAUDE.md` (5.3 KB) — Claude Code 项目指引（架构 + 常见改动模式）
- `README.md` (3.5 KB) — 项目入口文档（功能概述、启动指引）
- `_packer_entry_backend.py` (0.2 KB) — Nuitka 打包入口（暴露 backend.main:app）
- `video-material-insert-system.py` (5.0 KB) — 顶层启动器（含 DB 加密密钥嵌入）
- `nuitka-crash-report.xml` (4.1 MB) — Nuitka 打包崩溃报告（可清理）
- `video_material_system.db` (40 KB) — 旧版数据库（运行时不再使用，已迁移到 `data/database.db`）

## backend/

### backend/ 根

- `main.py` (2.9 KB) — FastAPI 应用入口（路由注册 + 静态文件挂载 + 启动钩子）
- `requirements.txt` (0.3 KB) — Python 依赖清单
- `.env` (0.3 KB) — 本地环境变量（**不入库**，用于覆盖默认配置）
- `.env.example` (0.6 KB) — 环境变量模板（HOST / PORT / FFMPEG_BIN 等）
- `.packer_deps_hash` (32 B) — 打包依赖哈希
- `__init__.py` (13 B) — 包标记
- `app/__init__.py` (13 B) — 包标记

### backend/app/api/ — API 路由

- `__init__.py` (13 B) — 包标记
- `audit.py` (1.8 KB) — 操作审计日志查询接口
- `auth.py` (2.2 KB) — 登录鉴权 + JWT 签发
- `configs.py` (5.0 KB) — 模板（关键词配置）的 CRUD + 导入导出
- `materials.py` (25.2 KB) — 素材库（产品 / 脚本目录 / 素材文件）的 CRUD + 上传 + 预览
- `roles.py` (3.1 KB) — 混剪角色定义的 CRUD
- `rough_cut.py` (17.4 KB) — 混剪项目 / 资产 / 时间线 / 导出 / ASR 重试 等全部端点
- `settings.py` (5.3 KB) — 系统设置 GET/PUT + ASR 模型 check/install/cancel/list/delete + FFmpeg 工具检视
- `source_videos.py` (11.9 KB) — 源视频条目上传 + ASR 触发 + 字幕预览/下载
- `stats.py` (1.5 KB) — 控制台首页统计（任务 / 素材 / 混剪项目）
- `tasks.py` (12.0 KB) — 素材插入任务的 CRUD + 重试 + 停止 + 输出/报告/日志下载
- `users.py` (2.8 KB) — 用户管理（创建 / 删除 / 改密 / 模块权限）

### backend/app/middleware/ — 中间件

- `__init__.py` (0 B) — 包标记
- `audit_middleware.py` (6.0 KB) — 请求审计日志拦截器
- `auth_middleware.py` (2.4 KB) — JWT 校验（含 `?token=` query fallback）

### backend/app/models/ — SQLAlchemy ORM 模型

- `__init__.py` (0.1 KB) — 模型聚合导出
- `audit_log.py` (1.3 KB) — 审计日志表
- `config.py` (0.1 KB) — 兼容占位（旧）
- `config_template.py` (0.7 KB) — 关键词模板表
- `database.py` (21.7 KB) — DB 引擎 + Session + 启动时 schema 兼容性迁移（all ALTER TABLE 都在这）
- `material.py` (1.6 KB) — 素材文件元数据表
- `material_folder_binding.py` (1.0 KB) — 素材到脚本目录的多对多绑定
- `material_product.py` (0.8 KB) — 素材产品分类（顶级目录）
- `material_script_folder.py` (1.2 KB) — 产品下脚本子目录
- `role_definition.py` (0.7 KB) — 混剪角色定义（A/B/C 等）
- `rough_cut_project.py` (2.6 KB) — 混剪项目主表（脚本/角色/素材/时间线/状态）
- `settings.py` (1.1 KB) — 全局系统设置（输出格式 / ASR 模型 / 视频编码器 等）
- `source_video_entry.py` (1.9 KB) — 源视频条目表（视频路径 / ASR 状态 / 字幕路径）
- `task.py` (1.8 KB) — 素材插入任务主表
- `task_snapshot.py` (0.8 KB) — 任务执行时的模板配置快照
- `user.py` (0.7 KB) — 用户账号表

### backend/app/schemas/ — Pydantic 请求 / 响应模型

- `__init__.py` (13 B) — 包标记
- `audit.py` (0.6 KB) — 审计日志响应
- `auth.py` (0.9 KB) — 登录请求/响应
- `common.py` (0.1 KB) — 通用枚举
- `config.py` (2.0 KB) — 模板 schema
- `material.py` (1.8 KB) — 素材 schema
- `role.py` (1.1 KB) — 角色 schema
- `rough_cut.py` (6.5 KB) — 混剪项目所有 schema（含 RoleAsset、TimelineClip 等）
- `settings.py` (2.1 KB) — 系统设置 + ASR 安装 + FFmpeg 检视 schema
- `source_video.py` (1.3 KB) — 源视频条目 schema
- `task.py` (1.7 KB) — 任务 schema

### backend/app/services/ — 业务逻辑

- `__init__.py` (13 B) — 包标记
- `asr_install_service.py` (10.6 KB) — ASR 模型异步下载（子进程化、可取消）+ 列表 / 删除
- `asr_service.py` (16.6 KB) — faster-whisper 调度（CUDA 检测、compute_type 解析、词级时间戳）
- `auth_service.py` (0.9 KB) — JWT 编解码 + 密码哈希
- `ffmpeg_service.py` (3.9 KB) — FFmpeg / FFprobe 二进制检视（路径、版本、硬件编码器）
- `material_service.py` (13.4 KB) — 关键词匹配 + 冲突优先级解析 + 素材文件查找
- `report_service.py` (1.9 KB) — 任务执行报告（XLSX）生成
- `rough_cut_service.py` (107.3 KB) — 混剪项目核心：脚本拆分 / 角色 ASR / 时间线 / 渲染（最大单文件）
- `subtitle_service.py` (1.2 KB) — SRT 解析（带时间偏移）
- `task_service.py` (29.9 KB) — 素材插入任务流水线：FFmpeg 编排 / 并发信号量 / 关键词冲突
- `video_service.py` (15.9 KB) — FFmpeg 命令构建 + 视频探测 + 输出运行

### backend/app/utils/ — 工具

- `__init__.py` (13 B) — 包标记
- `csv_utils.py` (6.5 KB) — 模板 CSV 导入导出 + 行解析
- `encoder_utils.py` (3.7 KB) — FFmpeg 硬件编码器探测（NVENC / QSV / AMF）+ 参数构建
- `ffmpeg_utils.py` (0.3 KB) — FFmpeg 路径辅助
- `file_utils.py` (6.4 KB) — 跨平台路径标准化（避免 Windows / Linux 拼接 bug）
- `logger.py` (0.6 KB) — Loguru 配置（含 ASR 滚动日志）
- `srt_utils.py` (0.1 KB) — SRT 工具占位

### backend/app/ 顶层

- `config.py` (1.8 KB) — Settings dataclass + .env 加载
- `dependencies.py` (0.3 KB) — FastAPI DI（DB session、Settings）

### backend/tests/ — 测试

- `__init__.py` (13 B) — 包标记
- `test_csv_utils.py` (2.3 KB) — CSV 解析测试
- `test_material_service.py` (4.2 KB) — 关键词匹配测试
- `test_rough_cut_service.py` (1.8 KB) — 混剪服务测试
- `test_subtitle_service.py` (0.5 KB) — SRT 解析测试
- `test_task_service.py` (6.4 KB) — 任务流水线测试
- `test_video_service.py` (4.3 KB) — FFmpeg 命令构建测试

## frontend/

### frontend/ 根

- `index.html` (0.6 KB) — Vite 入口 HTML
- `package.json` (0.5 KB) — npm 依赖与脚本
- `package-lock.json` (100.7 KB) — npm 锁文件
- `postcss.config.js` (81 B) — Tailwind PostCSS 配置
- `tailwind.config.js` (0.4 KB) — Tailwind 配置
- `vite.config.js` (0.2 KB) — Vite 配置（dev 代理 /api → :8000）

### frontend/public/ — 静态资源

- `bzy_logo.png` (716 KB) — 八爪鱼 Logo
- `favicon.ico` (0.2 KB) — 网站图标
- `login-bg.mp4` (5.5 MB) — 登录页背景视频

### frontend/src/ — Vue 源码

- `App.vue` (2.8 KB) — 根组件（路由 + 主题切换 + 侧栏切换）
- `main.js` (0.5 KB) — Vue 应用入口

### frontend/src/api/ — 后端 API 包装

- `audit.js` (1.0 KB) — 审计日志 API
- `auth.js` (0.2 KB) — 登录 API
- `config.js` (0.9 KB) — 模板 API
- `index.js` (1.5 KB) — Axios 实例 + 401 拦截 + `withAuthToken` 辅助
- `material.js` (2.2 KB) — 素材 API
- `roles.js` (0.3 KB) — 角色 API
- `roughCut.js` (5.7 KB) — 混剪项目 API
- `settings.js` (1.3 KB) — 系统设置 + ASR 模型管理 + FFmpeg 检视 API
- `sourceVideo.js` (1.5 KB) — 源视频条目 API
- `task.js` (2.4 KB) — 任务 API
- `users.js` (0.3 KB) — 用户管理 API

### frontend/src/assets/styles/

- `global.css` (17.1 KB) — 全局样式（亮 / 暗 / 玻璃 三主题 + 动画）

### frontend/src/components/

- `common/ExecutionMetaTags.vue` (1.1 KB) — 任务执行环境标签（模型/精度/编码器/尺寸）
- `common/FileUpload.vue` (0.8 KB) — 文件上传组件
- `common/GridSelector.vue` (1.9 KB) — 5×5 九宫格位置选择器
- `common/ProgressBar.vue` (0.9 KB) — 进度条（支持呼吸动画）
- `common/StatusTag.vue` (0.7 KB) — 状态标签（待处理/处理中/已完成/失败）
- `layout/Header.vue` (5.4 KB) — 顶栏（用户菜单 + 主题切换）
- `layout/Sidebar.vue` (6.1 KB) — 侧栏导航（两层可折叠树）
- `task/CreateTaskModal.vue` (16.5 KB) — 新建任务弹窗（模板选择 + 冲突预检）
- `task/TaskTable.vue` (5.5 KB) — 任务表格（含执行环境标签）

### frontend/src/router/

- `index.js` (2.2 KB) — Vue Router 配置 + 鉴权守卫

### frontend/src/store/ — Pinia

- `index.js` (0.1 KB) — Pinia 入口
- `modules/auth.js` (1.7 KB) — 认证状态（登录态 + 模块权限）
- `modules/config.js` (0.9 KB) — 模板 store
- `modules/material.js` (2.1 KB) — 素材 store
- `modules/sourceVideo.js` (1.3 KB) — 源视频 store
- `modules/task.js` (1.0 KB) — 任务 store

### frontend/src/utils/

- `constants.js` (62 B) — 前端常量
- `format.js` (0.3 KB) — 时间 / 文件大小格式化
- `validate.js` (0.1 KB) — 表单校验

### frontend/src/views/ — 页面

- `AuditLog.vue` (9.5 KB) — 操作历史页
- `ConfigEditor.vue` (18.8 KB) — 模板编辑器（行级 5×5 九宫格 + 素材联动）
- `ConfigList.vue` (2.1 KB) — 模板列表
- `Home.vue` (11.6 KB) — 控制台首页（统计卡 + 工作流 + 最近任务）
- `Login.vue` (9.7 KB) — 登录页
- `MaterialLibrary.vue` (23.7 KB) — 素材库（产品 / 脚本目录 / 拖拽归档）
- `RoughCutMultiRole.vue` (50.5 KB) — 多角色混剪旧页（已被 RoughCutUnit 替代，保留兼容）
- `RoughCutUnit.vue` (69.5 KB) — 混剪单元（单页面：脚本/角色/素材/时间线/预览）
- `Settings.vue` (19.2 KB) — 系统设置 + FFmpeg 工具管理 + ASR 模型管理
- `SourceVideoLibrary.vue` (15.8 KB) — 源视频库
- `TaskDetail.vue` (7.7 KB) — 任务详情页
- `TaskList.vue` (3.7 KB) — 任务管理列表
- `UserManagement.vue` (16.6 KB) — 用户管理（管理员）

## electron/

- `main.js` (3.0 KB) — Electron 主进程（窗口 + 菜单 + IPC）
- `package.json` (1.0 KB) — Electron 桌面端依赖

## scripts/

- `build_executable.py` (0.3 KB) — Nuitka 打包脚本
- `e2e_verify.ps1` (6.6 KB) — 端到端冒烟测试（PowerShell）
- `precheck.sh` (20.8 KB) — 启动前预检（Python/Node/.venv/FFmpeg/ASR/DB/端口）
- `start_all.bat` (0.5 KB) — 一键启动（Windows）
- `start_all.sh` (0.7 KB) — 一键启动（Linux/Mac）
- `start_backend.bat` (0.5 KB) — 仅后端（Windows）
- `start_backend.sh` (0.8 KB) — 仅后端（Linux/Mac）
- `start_frontend.bat` (0.2 KB) — 仅前端（Windows）
- `start_frontend.sh` (0.1 KB) — 仅前端（Linux/Mac）
- `stop_all.sh` (7.4 KB) — 强力关停（按命令行 + 端口 + DB 锁清理）

## tools/

- `ffmpeg/ffmpeg.zip` (103.7 MB) — FFmpeg 8.1 essentials_build 安装包（解压后产生 `ffmpeg-8.1-essentials_build/`，已在 `.gitignore` 排除）

## docs/ — 历史变更记录与架构文档

> 大部分为按时间戳归档的实施记录，浏览时按文件名前缀的日期定位即可。

- `API接口文档.md` (6.4 KB) — REST API 总览
- `技术架构与技术栈.md` (0.7 KB) — 技术栈说明
- `部署指南.md` (3.2 KB) — 生产部署说明
- `项目开发文档.md` (2.3 KB) — 开发约定
- `20260420_*.md` ~ `20260426_*.md`（**52 篇**）— 按时间归档的功能/修复实施记录
  - 主题覆盖：侧栏 / 模板 / 任务 / 字幕 ASR / 素材库 / 多角色混剪 / 暗色模式 / 登录 / 审计 / RBAC

## plan-md/ — 设计稿

- `20260422_codex_多角色口播粗剪_UIUX实施说明.md` (16.7 KB) — 多角色混剪 UI/UX 设计稿（codex 协作）

---

## 体积概览

| 类别 | 文件数 | 体积 |
|---|---|---|
| 后端 Python（不含测试）| 50 | ~340 KB |
| 后端测试 | 6 | ~20 KB |
| 前端 Vue/JS | 47 | ~360 KB |
| 全局样式 | 1 | 17 KB |
| 公共静态资源 | 3 | 6.2 MB（含登录视频）|
| 脚本 | 10 | ~37 KB |
| 文档 | 56 | ~120 KB |
| 工具二进制 | 1 | 103.7 MB（ffmpeg.zip）|

**核心代码（不含静态资源、文档、二进制）**：约 **750 KB / 110 个源文件**。
