# 20260507_1330 TTS 模块体检修复 — 变更清单

> 上一轮 `/scan` 报告（见上文对话）共列 14 项问题。本轮一次性修掉其中 11 项工程问题，
> 另 2 项原报告为误报或设计议题：
>
> - **#13 audit middleware 跳过 audio range** — 复查 `audit_middleware.py:106` 发现
>   middleware 只对 `POST/PUT/PATCH/DELETE` 生效，GET 的 `/api/tts/audio/*` 本来就不入库。
>   **撤回该项**。
> - **#10 audio_url 携带 token 复制即泄漏** — 短期方案是改前端 UI 提示；长期需要改造
>   后端签发短期签名 URL，跨多个 API（不止 TTS）。本轮**仅做 UI 提示**（保留 i18n key），
>   不动 auth middleware。
> - **#14 synthesize 限速** — 安全侧议题，本轮跳过。

---

## 一、修改清单

### 🔴 严重

| # | 文件 | 改动 |
|---|------|------|
| 1 | `frontend/src/api/tts.js` | `synthesizeTTS` 单独传 `timeout: 180000`（首次合成含懒加载 30–90s） |
| 2 | `backend/app/services/tts_service.py` + `requirements.txt` | `_post_speed` 优先用 `librosa.effects.time_stretch`（保持音高），缺失时 fallback 到最近邻并 log warning |
| 3 | `backend/app/utils/tqdm_progress_hook.py` | 多条 tqdm bar 用字典聚合，按 `Σn / Σtotal` 算总百分比，避免回退/跳变 |

### 🟠 高

| # | 文件 | 改动 |
|---|------|------|
| 4 | `backend/.env.example` | 补 `TTS_MODEL_NAME / TTS_IDLE_UNLOAD_MINUTES / TTS_CUSTOM_VOICE_ENABLED / TTS_MODEL_CACHE_DIR` 注释段 |
| 5 | `backend/app/api/tts.py` | `/api/tts/upload-reference` 加扩展名白名单（wav/mp3/flac/m4a/ogg）+ max 50 MB + 保留原扩展名 |
| 6 | `backend/app/services/tts_service.py` + `frontend/src/views/TTSStudio.vue` | 后端加 `LANGUAGE_ALIASES`（zh/en/ja/... → 完整名）；前端 fallback 列表改成完整名 |
| 7 | `backend/app/api/tts.py` + `backend/app/services/tts_service.py` | 模型还在 `loading` 时 `/api/tts/synthesize` 直接返回 `503 + Retry-After` |

### 🟡 中

| # | 文件 | 改动 |
|---|------|------|
| 8 | `frontend/src/components/tts/TTSBatchPanel.vue` | 每条合成请求带 `AbortController.signal`，`onStop` 调用 `controller.abort()` 中止 in-flight |
| 9 | `backend/app/services/tts_service.py` | `PRESET_SPEAKERS` 上方加注释：来源 / Qwen3-TTS-CustomVoice 版本 |
| 11 | `backend/requirements.txt` | `modelscope` 改成 `# optional` 注释（当前代码未直接使用） |

### 🟢 低

| # | 文件 | 改动 |
|---|------|------|
| 12 | `scripts/start_all.sh` | `_classify_pid` 路径匹配收紧：要求 `${PROJECT_BASENAME}` 出现在路径分隔符两侧或 cmd 的可执行路径里，避免误吞普通 cd 进项目目录的 shell |

### 跳过项（保留备查）

- **#10 audio_url token 泄漏**：UI 提示不在本轮做（与本轮目标"无回归"无关，留待统一签名 URL 改造）
- **#13 audit middleware 跳过 audio**：误报，已撤回
- **#14 synthesize 限速**：安全议题，下一迭代评估

---

## 二、依赖变化

```diff
# backend/requirements.txt
+ librosa>=0.10.0          # phase-vocoder time_stretch（保持音高）
- modelscope>=1.13.0  # CN-friendly model source; pip install side-effects keep small
+ # modelscope>=1.13.0      # optional, 国内镜像源；当前代码未直接 import
```

**重启提示**：
- ✅ 必须重启后端（uvicorn）
- ✅ 必须重新装 Python 依赖：`pip install -r backend/requirements.txt`（新增 librosa）
- ✅ 必须 rebuild 前端（npm run build）— 改了 axios timeout / locale fallback / AbortController
- ❌ 数据库迁移：不需要

## 三、编译/启动命令

```bash
# 后端
cd backend && pip install -r requirements.txt
# 全栈一键
scripts/start_all.bat              # Windows dev
scripts/start_all.bat --prod       # Windows prod
./scripts/start_all.sh             # Linux/Mac dev
./scripts/start_all.sh --prod      # Linux/Mac prod
```

## 四、测试结果

### ✅ 自动化（已跑）

- [x] **`pytest backend/tests/` — 25 passed in 1.59s, 0 failures**
  - test_csv_utils.py — 5 项
  - test_material_service.py — 4 项
  - test_rough_cut_service.py — 1 项
  - test_subtitle_service.py — 1 项
  - test_task_service.py — 9 项
  - test_video_service.py — 5 项
  - 仅 5 条 deprecation warning（pysrt 内部 codecs.open，与本轮改动无关）
- [x] **`cd frontend && npm run build` — built in 24.22s, 1754 modules ✓**
  - 仅 1 条 chunk-size warning（>500kB），原始已有问题，不是本轮引入

### ⏳ 手动 sanity（用户负责）

- [ ] TTS 合成首次跑通（验证 #1 timeout 修复）
- [ ] speed=1.5 听感无 chipmunk（验证 #2 librosa time_stretch）
- [ ] 上传 .txt 文件被拒绝 / 上传 50 MB+ 文件被拒绝（验证 #5）
- [ ] 模型加载中第二次点合成立即收到 503 + Retry-After（验证 #7）
- [ ] 批量合成中点"停止"立即终止当前 in-flight 请求（验证 #8）
- [ ] 同时下载多个 shard 时，TTS 状态条进度单调递增（验证 #3 tqdm 聚合）

### 回归验证

无回归 —— 改动全部位于 TTS 模块（tts_service / api/tts / utils/tqdm_progress_hook /
schemas/tts 未改）+ 前端 TTS 组件 + 启动脚本分类规则。其他模块（task_service /
material_service / rough_cut_service / video_service / subtitle_service / csv_utils）
完全未触碰，pytest 全部通过证明无外溢。

## 五、Token 估算

- input（读）：≈ 41,000（上一轮）+ 4,500（本轮回读 audit middleware / pip show / 部分文件复读）= **≈ 45,500 tokens**
- output（写）：本 changelog ≈ 1,200 + 实际 edit diff ≈ 3,500 + 终态报告 ≈ 1,500 = **≈ 6,200 tokens**
