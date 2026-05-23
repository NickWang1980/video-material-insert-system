# 20260506_1115 — TTS 模块前端集成完成（changelog）

## 范围

按 `docs/20260506_0933_tts_frontend_plan.md` 计划完成 A 必做 + 全部 B 选做 + 中英双语 i18n。

## 新增文件（13）

| 文件 | 行数 | 说明 |
|------|------|------|
| `frontend/src/api/tts.js` | ~76 | 9 端点 Axios wrapper + `getTTSAudioUrl()` 容错（4 种输入格式） |
| `frontend/src/store/modules/tts.js` | ~188 | Pinia options API store，含轮询、enum 缓存、历史持久化（localStorage `vmis_tts_history`，最多 50 条） |
| `frontend/src/views/TTSStudio.vue` | ~510 | 主页面 — 头部+模型状态条+左主输入区+右历史栏+批量折叠面板+保存对话框 |
| `frontend/src/components/tts/TTSModelStatus.vue` | ~161 | 自包含状态卡片 + 加载/卸载按钮 + 2s 轮询 |
| `frontend/src/components/tts/TTSReferenceUploader.vue` | ~110 | 拖放上传参考音频 |
| `frontend/src/components/tts/TTSPresetVoicePicker.vue` | ~70 | 9 个预设音色卡片选择 |
| `frontend/src/components/tts/TTSAudioPlayer.vue` | ~70 | `<audio>` 包装 + 下载链接 + 存为素材按钮 |
| `frontend/src/components/tts/TTSBatchPanel.vue` | ~240 | .txt 上传 → 串行合成 → JSZip 客户端打包下载 |
| `frontend/src/components/tts/TTSHistoryList.vue` | ~110 | 历史记录展示 + 复用/播放/删除 |
| `frontend/src/locale/index.js` | ~40 | vue-i18n 实例 + setLocale/toggleLocale，本地化语言持久到 localStorage |
| `frontend/src/locale/zh-CN/tts.json` | ~95 | 中文 locale（仅 TTS 命名空间） |
| `frontend/src/locale/en-US/tts.json` | ~95 | 英文 locale（镜像 key 结构） |
| `docs/20260506_0933_tts_frontend_plan.md` | — | 计划落档 |

## 修改文件（4）

| 文件 | 改动 |
|------|------|
| `frontend/package.json` | + `vue-i18n@^10.0.5` + `jszip@^3.10.1` |
| `frontend/src/main.js` | `import i18n from "./locale"` + `app.use(i18n)` |
| `frontend/src/router/index.js` | + import + 路由 `/tts` → `TTSStudio.vue` |
| `frontend/src/components/layout/Sidebar.vue` | 在「素材插入」分组下加 `{ to: "/tts", label: "TTS合成", short: "音", moduleKey: "materials" }` —— 复用 materials moduleKey 不动后端权限 |
| `CLAUDE.md` | 加 What/Key services/Data Dir/Key Patterns/Common Patterns 5 处 TTS 段落 |

## 后端

零改动 — 之前提交 `98aa092 / 18d87be / c69829a` 已经把后端落地（`backend/app/api/tts.py`、`backend/app/services/tts_service.py` 等）。

## TTS Studio 主页面功能清单

- 顶部：标题 + 副标题 + 中/EN 切换按钮（仅切 TTS UI，不影响其他页面）
- 模型状态条：phase 标签 + 进度条 + elapsed + loaded chips + 加载 Base / 加载 CustomVoice / 卸载所有
- 文本输入：5000 字符上限 + 计数器 + show-word-limit
- 语言下拉（11 项，含 auto）+ 情感下拉（7 项）+ 自定义 instruct（覆盖情感）+ 语速滑块（0.5–2.0×）
- Tab 1 声音克隆：拖放上传参考音频；自动调 `/api/tts/upload-reference`，回填 `ref_audio_path`
- Tab 2 预设音色：9 个卡片网格，仅当 CustomVoice 已加载有效；选中高亮
- 合成按钮：loading 态、文本空时禁用、错误用 ElAlert 显示
- 结果区：`<audio controls>` 试听 + 下载（带 token） + 存为素材
- 右侧历史栏：localStorage 持久化，复用/播放/单条删除/清空全部（含二次确认）
- 底部批量面板：折叠默认，.txt 上传 → 串行合成 → 进度条 → JSZip 客户端打包下载（避免后端新接口）
- 保存到素材库对话框：`GET /api/materials/tree` 拉树 → 选 product → 选 script_folder → 拉 wav blob → `POST /api/materials` FormData 上传

## Token 估算（本轮）

- **Input（读）**：~38k — Qwen3-TTS 项目调研（2 个 Explore agent 报告）+ 主项目结构（router、Sidebar、material API、main.js、api 风格、store 风格、CLAUDE.md、materials.py）+ 4 个 sub-agent 返回
- **Output（写）**：~28k — 13 新文件 + 4 修改 + 计划 md + 本 changelog md + CLAUDE.md 5 处段落

## 影响 / CLI

| 项 | 是否需要 | 说明 |
|----|----------|------|
| 重启后端（uvicorn） | ❌ | 后端零改动 |
| 重 build 前端 | ✅ | 必须先 `npm install` 装 vue-i18n + jszip，再 `npm run build` |
| 数据库迁移 | ❌ | TTS 输出落 `data/outputs/tts/`，不入库 |
| 重装前端依赖 | ✅ | `cd frontend && npm install` |
| 重装后端依赖 | ❌ | requirements.txt 已就绪 |

### 启动命令

```bash
# 1) 前端依赖与构建
cd frontend
npm install                # 拉 vue-i18n + jszip
npm run dev                # 开发服 http://localhost:5173
# 或
npm run build              # 生产 build → frontend/dist/

# 2) 全栈启动
scripts/start_all.bat              # Windows 开发
scripts/start_all.bat --prod       # Windows 生产（FastAPI 静态托管 dist）
./scripts/start_all.sh             # Linux/Mac 开发
./scripts/start_all.sh --prod      # Linux/Mac 生产

# 3) 单跑后端
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

## 端到端验证（用户手动）

按计划文件「七、端到端验证」段执行 — AI 不代跑。

## 已知约束 / 后续可选优化

1. **moduleKey 复用 materials**：TTS 菜单沿用素材库权限。如需独立权限，需后端 `auth/role` 模型加 `tts` module 并改 Sidebar `moduleKey: "tts"`。
2. **批量合成串行**：每行串行调 `/synthesize`，避免后端排队冲突。后端有 `max=2` 并发上限，将来若放开可改前端并发。
3. **保存到素材库的产品/脚本树**：仅在 dialog 首次打开时拉一次。如果用户在另一个 Tab 新建了产品，本页面不会自动刷新；需关闭对话框再开。
4. **历史记录单设备**：localStorage 只存本机。若需跨端同步，需要后端历史 API。
5. **批量合成的 zip 文件名**：取自上传 .txt 的 stem。可考虑加时间戳避免重复下载覆盖。

## 文档同步

- `CLAUDE.md` 已加 5 处 TTS 段落
- `docs/20260506_0933_tts_frontend_plan.md`（计划）+ 本 changelog 已落档

任务完成。
