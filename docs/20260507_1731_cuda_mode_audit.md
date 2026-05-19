# 20260507_1731 CUDA 模式实现完整性体检（诊断报告）

> 范围：扫描整个项目，确认"CUDA 模式"是否在三个使用 GPU 的子系统中**全部完全实现**。
> 结论：**两套完整、一套部分实现**。下文逐项对比已实现 vs 缺口，不动代码、仅出诊断。

---

## 一、三套 CUDA 子系统现状一览

| 子系统 | 关键文件 | 设备探测 | 用户可选偏好 | 自动回退 | 状态可观测 | 评级 |
|---|---|---|---|---|---|---|
| ① **视频编码（FFmpeg / NVENC）** | `backend/app/utils/encoder_utils.py` + `frontend/src/views/Settings.vue` | ✅ 编译 + 运行时双探测（list_working_hw_encoders 实际编 1 帧） | ✅ `auto / cpu / cuda / qsv / amf` | ✅ 自动回退 libx264 | ✅ Settings 页有可用编码器提示 | **完全实现** ✅ |
| ② **ASR（faster-whisper / CTranslate2）** | `backend/app/services/asr_service.py` + `Settings.vue` | ✅ `ctranslate2.get_cuda_device_count()` + 进程级缓存 | ✅ `auto / int8 / float16 / float32`（int8 强制 CPU 不混 CUDA） | ✅ float16/32 → 找不到 CUDA 自动回退 CPU | ✅ `resolved_compute_label()` 输出 `"float16 (CUDA)"` 等 | **完全实现** ✅ |
| ③ **TTS（Qwen3-TTS / PyTorch）** | `backend/app/services/tts_service.py` + `frontend/src/components/tts/TTSModelStatus.vue` | ⚠️ `torch.cuda.is_available()`（硬编码自动） | ❌ **无**（用户不能手动选 CPU / fp16 / fp32） | ✅ 没 CUDA 自动 CPU+fp32 | ❌ `/api/tts/status` 不返回 device/dtype，前端看不到当前是不是真跑 CUDA | **部分实现** ⚠️ |

---

## 二、TTS CUDA 子系统的具体缺口

### 缺口 1（🔴 严重）：torch 默认装的是 CPU wheel，CUDA 永远不会被启用

`backend/requirements.txt:18`：
```
torch>=2.0.0
```
- pip 默认从 PyPI 拉，**Windows / Linux 上拉到的是 CPU wheel**（除非用户自己加 `--index-url https://download.pytorch.org/whl/cu121`）。
- 即便机器有 NVIDIA GPU，`torch.cuda.is_available()` 也会返回 False → `_detect_device_dtype()` 走 CPU 分支 → TTS 永远跑在 CPU。
- **没有任何文档 / 启动脚本 / precheck 提示用户怎么换成 CUDA wheel**。`scripts/precheck.sh:550-560` 只查了 `ctranslate2.get_cuda_device_count()`（给 ASR 用），torch 那一侧零检查。

参考：本机当前若是 `pip show torch` 看 Location，wheel 名里没有 `+cu118` / `+cu121` / `+cu124` 后缀就是 CPU 版。

### 缺口 2（🟠 高）：TTS 没有 device 偏好配置项

对比 ASR 已经有的 `asr_compute_type: auto/int8/float16/float32`：
- `backend/app/config.py` 没有 `tts_device` / `tts_dtype` 字段。
- `backend/.env.example` 没有 `TTS_DEVICE_MODE` 之类的注释段。
- `backend/app/services/tts_service.py:124 _detect_device_dtype()` 是写死的：
  ```python
  if torch.cuda.is_available():
      return "cuda", "float16"
  return "cpu", "float32"
  ```
  用户**无法**：
  - 手动强制 CPU（开发 / 调试用）
  - 在 GPU 显存不够 fp16 时手动降到 fp32 再上 CPU（其实 fp16 才省）
  - 在多卡机上指定卡号（`cuda:1`）

### 缺口 3（🟠 高）：`/api/tts/status` 不暴露 device 信息，前端不可见

`backend/app/schemas/tts.py:25 TTSStatusResponse` 字段：
```
phase / percent / detail / message / error / elapsed_sec / ready /
base_loaded / custom_loaded / loaded_models
```
没有 `device` / `dtype`。

`frontend/src/components/tts/TTSModelStatus.vue` 也只显示 phase + 已加载模型名，**用户看不到 TTS 是不是真跑在 CUDA 上**。
对照 ASR：Settings 页可以从 `compute_type` 立刻知道。

### 缺口 4（🟡 中）：TTS 服务没有"CUDA 不可用"的显式告警

`tts_service.py:124` 在回退 CPU 时只 swallow 异常 + 默默走 CPU，**只在 `_load_qwen_tts_model` 的 INFO 日志写 `device=cpu`**。
- 用户期望 GPU 跑 1.7B 模型（CPU 上几十秒一句、GPU 上 1-2 秒），跑慢了第一反应不是看日志。
- 应在启动 / 首次加载时 `logger.warning` 醒目提示"未检测到 CUDA torch，TTS 将在 CPU 跑（慢 10-50 倍）。如需加速，请重装 torch CUDA wheel"。

### 缺口 5（🟡 中）：`CLAUDE.md` 没写 TTS 的 CUDA 行为

`CLAUDE.md` 的 "Key Architectural Patterns / TTS lazy-loading" 段落只描述了懒加载、idle-unload、tqdm 进度，**完全没提 device 探测规则、CUDA 显存占用、torch wheel 选型**。新会话 / 新协作者进来无从知晓。

### 缺口 6（🟢 低）：precheck.sh 没验证 torch CUDA wheel

`scripts/precheck.sh` 第 550 行附近为 ASR 做了 `ctranslate2.get_cuda_device_count()`，但没为 TTS 做 `torch.cuda.is_available()`，导致首启时用户拿不到"检测到 N 卡但 torch 是 CPU 版"的早期提醒。

---

## 三、修复建议（按优先级，不动代码、待你拍板）

### 优先级 P0 — 必做才能算"CUDA 完全实现"

1. **配置层**：在 `config.py` 新增 `tts_device_mode: Literal["auto","cpu","cuda","cuda:0","cuda:1"] = "auto"` 与 `tts_dtype: Literal["auto","float16","bfloat16","float32"] = "auto"`，并对应 `.env.example` 注释段。
2. **服务层**：把 `_detect_device_dtype()` 改成 `_resolve_device_dtype(settings)`，参考 ASR 的 `_resolve_device_compute()`：尊重用户偏好、CUDA 不可用时回退 CPU 并 `logger.warning`。
3. **API / Schema**：`TTSStatusResponse` 加 `device: str` 与 `dtype: str` 字段，由 `_tts_state` 在加载完成时写入。
4. **前端 Settings 页**：仿照 ASR 的"compute_type 选择器" + "实际使用 X (CUDA/CPU)" 标签，新增 TTS device 选择 + 当前激活提示。
5. **前端 TTSModelStatus.vue**：在状态卡顶部显示 `device: CUDA (float16)` 或 `device: CPU (float32) — torch 未编译 CUDA 支持`。

### 优先级 P1 — 强烈建议

6. **依赖装机指引**：在 `requirements.txt` 顶部 / `CLAUDE.md` / `docs/` 加一段"如何装 CUDA torch wheel"：
   ```bash
   # NVIDIA + CUDA 12.1：
   pip install torch --index-url https://download.pytorch.org/whl/cu121
   # NVIDIA + CUDA 11.8：
   pip install torch --index-url https://download.pytorch.org/whl/cu118
   # AMD ROCm 或 Apple Silicon 走默认渠道
   ```
7. **precheck.sh** 给 TTS 加一条 `python -c "import torch; print(torch.cuda.is_available(), torch.version.cuda)"`，未通过时打 warn（不阻断）。

### 优先级 P2 — 锦上添花

8. **CLAUDE.md** 在 TTS lazy-loading 段补一句 "device 由 `tts_device_mode` 决定，默认 auto。CUDA 不可用时回退 CPU 并打 warn"。
9. （可选）支持多卡：`tts_device_mode = cuda:1`、`cuda:auto`（按显存余量挑卡）。本轮可不做。

---

## 四、若选择"补完"——预估工作量

| 工作 | 文件数 | 大致 LOC | 重启/build | 测试影响 |
|---|---|---|---|---|
| 配置 + service 改造 | 3（config / .env.example / tts_service） | +60 / -10 | ✅ uvicorn 重启 | 不破坏现有 ASR/视频编码逻辑 |
| Schema + API 透出 | 2（schemas/tts / api/tts） | +15 | ✅ uvicorn 重启 | 前端旧字段保持兼容 |
| 前端 Settings + TTSModelStatus | 3（Settings.vue / TTSModelStatus.vue / tts.json 双语） | +50 | ✅ npm run build | 仅 UI 增量，无回归 |
| precheck + CLAUDE.md + 装机文档 | 3（precheck.sh / CLAUDE.md / 新增 docs） | +30 | 无 | 文档型 |
| **合计** | **~11 文件** | **~155 LOC** | 后端重启 + 前端 rebuild | 无回归风险 |

---

## 五、当前状态（不动代码）

- ✅ 已扫描：tts_service / asr_service / encoder_utils / config / schemas / api / Settings.vue / TTSStudio.vue / TTSModelStatus.vue / store/tts.js / requirements.txt / .env.example / precheck.sh / 历史 docs
- ❌ 未修改任何源文件
- 📝 已生成本诊断报告

---

## 六、Token 估算（input 读 / output 写 拆分）

- input（读）：tts_service.py 590 行 + asr_service.py 160 行 + encoder_utils.py 150 行 + Settings.vue 局部 + 其他文件 ≈ **~12,000 tokens**
- output（写）：本诊断 md ≈ **~2,200 tokens**

---

## 七、下一步等你决定

A. **全部按优先级 P0+P1 补完**（推荐，工作量约 ~155 LOC、不引入回归）
B. **只补 P0 五项**（最低限度，让 TTS CUDA 进入"完全实现"档位）
C. **只补 P0 中的 1-3 项**（配置 + service + status 透出，前端展示后续再说）
D. **现状即可、不动**（接受 TTS 是"自动检测、用户无可视无可控"的状态）

请告知选哪一档，我据此再开干，并按你的协作规则给出：
- 具体改动清单（带时间戳 md）
- 编译 + 启动命令
- 重启 / rebuild / 依赖重装提示
- 进度百分比报告
