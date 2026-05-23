# 20260506_1120 — 启动脚本一键化（TTS 感知）计划

## 背景

TTS 前端集成新增 2 个 npm 依赖（vue-i18n、jszip），但现有 [scripts/start_frontend.sh](../scripts/start_frontend.sh) / [.bat](../scripts/start_frontend.bat) 只用 `[ ! -d node_modules ]` 判断要不要 `npm install`。已有 `node_modules` 但是旧的（不含 vue-i18n/jszip）的用户跑一键启动会直接挂在 dev server 启动阶段（Vite 找不到 vue-i18n 模块）。

后端 TTS 依赖（qwen_tts、torch、soundfile、numpy、modelscope）已在 `backend/requirements.txt` 里，[scripts/precheck.sh](../scripts/precheck.sh) 在 `pip show` 检查时缺哪个就跑 `pip install -r backend/requirements.txt`。但当前 `missing` 关键包白名单只列了 `fastapi uvicorn faster-whisper opencc-python-reimplemented PyJWT bcrypt`，缺 TTS 包不会触发整批重装。

## 范围

让 `scripts/start_all.sh` 和 `scripts/start_all.bat` 真正做到 **TTS 一键启动** —— 老 `node_modules` / 老 `.venv` 都能自动补齐 TTS 新依赖。

## 改动文件

| 文件 | 改动 |
|------|------|
| `scripts/start_frontend.sh` | 把"node_modules 存在就跳过 npm install"改成"检查 sentinel 包（vue-i18n + jszip）任一缺失就 `npm install`" |
| `scripts/start_frontend.bat` | 同上，Windows 等价 |
| `scripts/start_all.sh` | prod 模式 build 分支同步上述逻辑 |
| `scripts/start_all.bat` | prod 模式 build 分支同步 |
| `scripts/precheck.sh` | Python 依赖 missing 白名单加 `qwen_tts`；额外打印 TTS 模型状态信息（不自动下载，1.7 GB 太大） |

不动文件：
- `start_backend.sh` / `.bat` — 已经无条件跑 `pip install -r backend/requirements.txt`，TTS 后端依赖会被覆盖
- `precheck.sh` 其他段落
- `stop_all.sh` / `stop_all.bat`

## 不做

- ❌ 自动下载 Qwen3-TTS 模型（1.7 GB Base + 1.7 GB CustomVoice 太大；保持懒加载，由用户在 UI 点 "加载 Base" 触发）
- ❌ 强制每次 npm install（慢；只在关键依赖缺失时触发）
- ❌ 改 backend 端口冲突预检（已经识别 Qwen3-TTS standalone 占用 5000/8000 的情况）

## 影响

- 重启后端：❌
- 重 build 前端：取决于现状 — 若 `node_modules` 缺 vue-i18n 会自动重装
- 数据库迁移：❌
- 重装依赖：自动按需 — 不需要用户手动跑

## 验证（用户手动）

```bash
# 1. 删 node_modules 模拟新机器
rm -rf frontend/node_modules

# 2. 一键启动
./scripts/start_all.sh                      # Linux/Mac
scripts/start_all.bat                       # Windows

# 期望：
#   - precheck 通过
#   - frontend 自动跑 npm install（拉 vue-i18n + jszip）
#   - 浏览器打开 http://localhost:5173/login
#   - 登录后侧栏点 "TTS合成" 进入 TTS Studio
```

实施按串行 5 个文件改动 + 1 篇 changelog。
