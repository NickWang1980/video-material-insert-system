# 20260506_1120 — 启动脚本一键化（TTS 感知）changelog

## 改动清单

| 文件 | 改动 |
|------|------|
| `scripts/start_frontend.sh` | 重写依赖检查：从"看 `node_modules` 目录是否存在"改为"逐个检查关键包（vue / vue-router / pinia / element-plus / axios / **vue-i18n** / **jszip**）的 `node_modules/<pkg>/package.json` 是否存在"，缺一即触发 `npm install` |
| `scripts/start_frontend.bat` | 同上，Windows 批处理等价实现（for 循环 + `node_modules\%%P\package.json` 检查） |
| `scripts/start_all.sh` | prod 模式 build 分支同步上述 sentinel 检查（`-d node_modules ｜｜ npm install` → 关键包逐个检查） |
| `scripts/start_all.bat` | 同上，Windows 等价 |
| `scripts/precheck.sh` | (1) Python 依赖 missing 白名单加 `qwen_tts`、`soundfile` —— 缺任一触发 `pip install -r backend/requirements.txt`；(2) 新增 §6.5 TTS 模型状态段：检测 `data/qwen3_models/hub/models--Qwen--Qwen3-TTS-*/snapshots/*` 是否有 `.safetensors`/`.bin`，已缓存则 ✅，否则 info 提示"首次在 UI 点'加载'时自动下载 ~1.7 GB"（不自动下载，避免占用 3.4 GB 强行预热） |

## 设计要点

### 为什么用 sentinel 而非每次 `npm install`
- 每次跑 `npm install` 即使有 lock 也会扫描 100+ 包，慢（10–30 s）
- sentinel 检查纯文件存在性，几毫秒
- 关键包列表覆盖所有"项目核心 + TTS 新增"，新加依赖时只要把包名加到清单即可

### 为什么 `qwen_tts` 是 sentinel 而 `torch` 不是
- `qwen_tts` 体积小、安装快，缺失检测准确
- `torch` 体积大（2 GB），可能被项目无关依赖（comfyui、其它工程）共享。但 `qwen_tts` 缺失 → 触发整批 `pip install -r requirements.txt` → 一并补 torch
- 这样既精准又不重复安装

### 为什么不自动下载 Qwen3-TTS 模型
- Base 1.7 GB + CustomVoice 1.7 GB = 最高 3.4 GB
- 多数用户首次启动只是为了试用其它功能（混剪、素材、ASR），TTS 是按需功能
- `tts_service.py` 已经实现首次合成时自动下载 + tqdm 进度推 frontend，体验已足够好
- 在 precheck 强行预热反而拖慢首启 5–10 分钟（看带宽）

## 影响

| 项 | 是否需要 | 说明 |
|----|----------|------|
| 重启后端 | ❌ | 后端零改动 |
| 重 build 前端 | ❌ | 脚本本身改动，下次启动时生效 |
| 数据库迁移 | ❌ | |
| 重装依赖 | 自动 | 旧 node_modules 用户首次跑会自动 npm install |

## 启动 CLI（一键）

```bash
# Linux/Mac
./scripts/start_all.sh                    # dev: backend:8000 + frontend:5173
./scripts/start_all.sh --prod             # prod: 单端口 8000，FastAPI 静态托管 dist
./scripts/start_all.sh --force-clean-foreign   # 顺便清理外部进程占用 8000/5173

# Windows
scripts\start_all.bat
scripts\start_all.bat --prod
```

## Token（本轮）

- **Input（读）**：~12k —— start_all.sh / precheck.sh / start_frontend.{sh,bat} / start_all.bat / start_backend.sh
- **Output（写）**：~3.5k —— 5 文件改 + 计划 md + 本 changelog

## 验证（用户手动，按规则不代跑）

```bash
# 模拟新机器：删 node_modules
rm -rf frontend/node_modules

# 一键启动
./scripts/start_all.sh

# 预期日志：
#   [precheck] ✅  Python 依赖已安装   或   ⬇️ Python 依赖缺失 (qwen_tts soundfile) — 正在安装...
#   [precheck] ℹ️ TTS 模型 Qwen3-TTS-12Hz-1.7B-Base — 未下载（首次在 UI 点 "加载" 时自动下载约 1.7 GB）
#   [start_frontend] 依赖缺失 — 正在 npm install ...
#   <Vite 启动 http://localhost:5173>
#   <浏览器自动打开 /login>

# 登录后 → 侧栏 "TTS合成" → 点 "加载 Base" 触发首次模型下载
```

任务完成。
