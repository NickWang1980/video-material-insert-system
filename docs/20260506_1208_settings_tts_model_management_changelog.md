# 20260506_1208 — 系统设置页加 TTS 模型管理（changelog）

## 范围

在「系统设置」页加 **TTS 模型管理（Qwen3-TTS）** 段，参照已有 ASR 模型管理 UX：表格列出 Base / CustomVoice 两个模型，每行显示缓存状态 / 内存加载状态 / 操作按钮（下载并加载、加载到内存、删除磁盘缓存），右上角"卸载所有"按钮。

## 改动文件（5）

### 后端
| 文件 | 改动 |
|------|------|
| `backend/app/schemas/tts.py` | 加 `TTSModelInfo` / `TTSModelListResponse` / `TTSModelDeleteResponse` |
| `backend/app/services/tts_service.py` | 加 `TTS_MODEL_KEYS` / `TTS_MODEL_LABELS` / `TTS_MODEL_DESCRIPTIONS` 字典；加 helper `_hf_cache_dir_name` / `_get_model_cache_dir` / `_dir_size_bytes` / `_is_model_cached` / `_is_model_loaded`；加公共函数 `list_models_info(settings)` / `delete_model_cache(settings, key)` |
| `backend/app/api/tts.py` | 加路由 `GET /api/tts/models` / `DELETE /api/tts/models/{key}` |

### 前端
| 文件 | 改动 |
|------|------|
| `frontend/src/api/tts.js` | 加 `listTTSModels` / `deleteTTSModel` 包装 |
| `frontend/src/views/Settings.vue` | 加 "TTS 模型管理（Qwen3-TTS）" 整段 UI + 5 个 handler（loadTTSModels / onDownloadTTSModel / confirmDeleteTTSModel / onUnloadAllTTS）；onMounted 并行加载列表 |

## 设计要点

### 后端
- **磁盘缓存检测** (`_is_model_cached`)：从 `data/qwen3_models/hub/models--Qwen--Qwen3-TTS-*/snapshots/<rev>/` 下找 `.safetensors`/`.bin`/`.pt` 任意一种，存在即视为已缓存。这避免了空目录 / 残缺下载误报为已缓存。
- **内存加载检测** (`_is_model_loaded`)：扫 `_tts_model_cache` 字典 key（包含 device/dtype 三元组），匹配 model_id 即返回 True。
- **删除前先 unload**：rmtree 前先把对应 model_id 的缓存条目从 `_tts_model_cache` 弹出 + `gc.collect()` + `torch.cuda.empty_cache()`，避免 Windows 文件占用导致删除失败。
- **下载触发**：复用现有 `/api/tts/load` 和 `/api/tts/load-custom` —— 它们会 `Qwen3TTSModel.from_pretrained(...)`，HuggingFace Hub 自动下载到 cache 后实例化。无需新加 "仅下载不加载" 端点。

### 前端
- **行内动作锁**：用 `ttsActing` reactive 对象 keyed by row.key，分别记录 `'download'` / `'delete'`，避免按钮 loading 状态串扰。
- **按钮文案随状态变化**：
  - 未缓存 + 未加载 → "下载并加载"
  - 已缓存 + 未加载 → "加载到内存"
  - 已加载 → 隐藏（仅显示 "删除磁盘缓存"）
- **CustomVoice 启用门**：`tts_custom_voice_enabled=False` 时，按钮 disabled + 显示"未启用"红 tag，提示用户改 `backend/.env` 后重启。
- **下载进度**：不在 Settings 页内做进度条（避免重复轮询逻辑），而是引导用户去 TTS Studio 看模型状态条。Settings 页面只在 1.5 s 后刷新一次列表。
- **运行时占用估算**：`download_size_mb × 2`，对应 fp16 显存（fp32 ≈ ×4，但默认 GPU + fp16，给出贴近常见情况的估算）。

## 影响

| 项 | 是否需要 |
|----|----------|
| 重启后端 | ✅ **必须** — 新增了 2 条路由 + 多个 service 函数 |
| 重 build 前端 | ✅ **必须** — Settings.vue 改动 + api/tts.js 加新方法 |
| 数据库迁移 | ❌ |
| 重装依赖 | ❌ |

### 启动 CLI

```bash
# 后端：杀掉旧进程，重启
# Windows
scripts\start_all.bat
# Linux/Mac
./scripts/start_all.sh

# 仅前端 build
cd frontend && npm run build

# Dev 模式 Vite 会热更新前端，但后端要手动 ctrl+c 后重跑 uvicorn
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

## 验证（用户手动，按规则不代跑）

1. 打开「系统设置」页，滚到底部看到 "TTS 模型管理（Qwen3-TTS）" 段，两行：Base / CustomVoice。
2. 第一次进入预期：两个模型都显示 "未下载"。
3. 点 Base 行的 "下载并加载" → 跳消息提示"已开始下载并加载 Base（约 1700 MB）"；切到 TTS 合成页看进度条。
4. 1–10 分钟后回 Settings 点"刷新"，Base 应显示 "已缓存到磁盘" + "已加载到内存"，磁盘占用接近 1.7 GB。
5. 点 "卸载所有" → Base 仅保留 "已缓存"。
6. 点 Base 的 "删除磁盘缓存" → 二次确认 → 删除成功，模型回到 "未下载" 状态。
7. CustomVoice 行：默认 `tts_custom_voice_enabled=False`，按钮 disabled，红 tag "未启用"。在 `backend/.env` 加 `TTS_CUSTOM_VOICE_ENABLED=1` 后重启后端，再刷新即可启用。

## Token（本轮）

- **Input（读）**：~22k —— Settings.vue / settings.py / settings.js / config.py
- **Output（写）**：~9k —— 5 文件改 + 本 changelog

任务完成。
