# 高优先级修复变更日志（H1–H8）

**日期**：2026-05-13
**触发**：从 `3.1-GPU-enabled/3.0-adding-tts-module` 合并入当前分支后的代码扫描，挑出 8 条 🔴 高优先级问题并修复。
**对应扫描报告**：`docs/`（未单独导出，详见 `C:\Users\techm\.claude\plans\purring-sprouting-sunbeam.md` 中的"完整问题清单"）

---

## 一、修复条目逐项

### H1. TTS 加载线程超时竞态修复

- **文件**：`backend/app/services/tts_service.py`
- **改动**：
  - 新增模块级 `_tts_load_errors: dict[tuple, Exception]` 和 `_tts_load_lock: threading.Lock`
  - 加载线程内 try/except：失败时写入错误字典 → `event.set()` 在 finally
  - `event.wait()` 返回后先查错误字典，有错误就清状态并 raise 友好 `RuntimeError`；无错误但缓存空时同样清状态并 raise（避免死循环）
- **效果**：加载失败后下次调用可重试，不再陷入"必须重启进程"状态。

### H2. TTS device/dtype 全局化

- **文件**：`backend/app/services/tts_service.py`
- **改动**：
  - 新增 `_TTS_DEFAULT_DEVICE`、`_TTS_DEFAULT_DTYPE`、`_TTS_GLOBAL_DETECT_LOCK`
  - 新增 `_ensure_default_device_dtype()`（double-checked locking，首次调用时探测一次）
  - `get_or_load_tts()` 与 `is_loading_in_progress()` 全部改用全局默认
  - `get_or_load_tts()` 新增 kw-only `device` / `dtype_str` 参数，调用方可覆盖
- **效果**：并发线程不再因瞬时 `torch.cuda.is_available()` 差异落到不同 device 上，避免多份模型驻留。

### H3'. `_PyTorchWhisperWrapper` 返回值校验

- **文件**：`backend/app/services/asr_service.py`
- **改动**：
  - 新增辅助 `_safe_float` 与 `_probe_audio_duration`
  - 三段 fallback：`result["chunks"]` → `result["segments"]` → `result["text"]`，每段独立 try/except
  - 整段 `text` fallback 时用 soundfile 探测真实时长，失败给 60s 保守占位
  - 全部缺失时抛 `RuntimeError("Whisper 返回格式无法解析：...")`，便于排障
- **效果**：transformers pipeline 新旧版本返回结构差异不再导致 AttributeError。

### H4. CUDA DLL 通配检测（bash + python 两侧）

- **文件**：
  - `scripts/precheck.sh`（第 4.5 段 `check_cuda_dlls()`，约 391–510 行）
  - `backend/app/services/asr_service.py`（`_check_cuda_dlls`，约 87–160 行）
- **改动**：
  - 硬编码 `cudart64_120.dll` / `cublas64_120.dll` 等改为通配模式 `cudart64_12*.dll`、`cublas64_12*.dll`、`cublasLt64_12*.dll`、`cudnn64_*.dll`
  - bash 侧通过 python heredoc 用 `glob.glob` + `ctypes.WinDLL` 真正"试加载"，并打印 `ctranslate2.get_cuda_device_count()` 与 `torch.cuda.is_available()`
  - python 侧同步用 `glob` 通配 + `ctypes.WinDLL` 实际加载验证；保留经典命名兜底
  - 缺失只 `log_warn` 不阻断启动，保留"int8 绕过 / pip nvidia-cublas-cu12 / 装 CUDA Toolkit"三方向提示
- **效果**：CUDA 12.4 / 12.5 等副号环境不再误报缺失。

### H5. `backend/requirements.txt` 依赖上界

- **文件**：`backend/requirements.txt`
- **改动**：
  - 顶部新增三角兼容说明注释
  - 新增上界：
    - `qwen_tts>=0.1.0,<0.2.0`
    - `torch>=2.0.0,<2.7`
    - `faster-whisper>=1.1.0,<2.0`
    - `transformers>=4.41.0,<5.0`
    - 注释中 `modelscope` 加 `,<2.0`（保持注释状态）
  - `ctranslate2` 未在文件中显式列出（被 `faster-whisper` 传递引入），按"只锁已写依赖"原则未主动添加。如需冻结建议后续加 `ctranslate2>=4.0,<5.0`
- **效果**：未来 `pip install` 不会被大版本意外升级打破三角。

### H6. TTSModelStatus 轮询自清理（引用计数）

- **文件**：
  - `frontend/src/store/modules/tts.js`
  - `frontend/src/components/tts/TTSModelStatus.vue`
  - `frontend/src/views/TTSStudio.vue`
- **改动**：
  - store 顶部新增非响应式 `_pollingRefs` / `_pollingTimer`
  - `startPolling()` 每次 +1，仅在 timer 不存在时真启动
  - `stopPolling()` -1，归零时才真清
  - 新增 `forceStopPolling()` 作为 HMR 逃生口
  - `TTSModelStatus.vue`：增加 `onBeforeUnmount(() => store.stopPolling())`
  - `TTSStudio.vue`：`onMounted` 增加 `store.startPolling(2000)` 让引用计数对称
- **效果**：多次进出 TTS 页面不再叠加轮询请求。

### H7. localStorage QuotaExceededError 处理

- **文件**：`frontend/src/store/modules/tts.js`
- **改动**：
  - `_saveHistory()` 显式判断 `QuotaExceededError` (code 22) 与 `NS_ERROR_DOM_QUOTA_REACHED` (code 1014)
  - 配额超限：先 trim 至当前长度 50% 重试；仍失败则 console.warn 并暴露 `historyOverflow` flag
  - 新增内部 action `_persistHistory()` 同步 trim store 内的 history 数组
  - 新增 `acknowledgeHistoryOverflow()` 供 UI 重置 flag
- **效果**：localStorage 满载不再静默吞错；UI 层可 watch flag 显示提示。

### H8. `.claude/settings.local.json` 权限收敛

- **文件**：`.claude/settings.local.json`
- **改动**：
  - 删除 16 条含明文凭证 / 个人家目录绝对路径 / 一次性 PID 引用 / 域错放 PowerShell 命令的条目
  - 改写 1 条：`Bash(git -C "<abs path>" ls-files)` → `Bash(git ls-files)`
  - 条目数：60 → 40，全部为通用、项目相关命令模式
- **效果**：减少敏感信息泄漏面、降低权限白名单宽度。

---

## 二、需用户执行的操作

| 操作 | 必要性 | 命令 |
|------|--------|------|
| **重启后端** | ✅ 必需（tts_service / asr_service 已改） | `uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000` |
| **前端重新构建**（生产） | ✅ 必需（store/components 已改） | `cd frontend && npm run build` |
| **前端热重载**（开发） | 可选（dev server 通常自动 HMR） | `cd frontend && npm run dev` |
| **重装依赖** | ✅ 建议（requirements.txt 加了上界） | `pip install -r backend/requirements.txt` |
| **数据库迁移** | ❌ 不需要（本次无 schema 变化） | — |
| **一键启动**（推荐） | 替代上面前两项 | `scripts/start_all.bat` 或 `scripts/start_all.bat --prod` |

### 验证清单（按计划文件，全部由用户执行）

- **H1**：触发 `/api/tts/load` 一次失败后，再次触发应能正常加载（不需重启）
- **H2**：日志中应只出现一次 `[TTS] global default device/dtype initialized`
- **H3'**：ASR 出错时应给出可读 `RuntimeError`，不再是裸 `AttributeError`
- **H4**：在 CUDA 12.4+ 环境跑 `bash scripts/precheck.sh`，不再误报 CUDA DLL 缺失
- **H5**：干净 venv 中 `pip install -r backend/requirements.txt` 能稳定安装
- **H6**：浏览器 Network 面板，多次进出 `/tts-studio`，`/api/tts/status` 请求间隔保持 ~2s 不叠加
- **H7**：填满 localStorage 后触发合成保存历史，应看到 `console.warn` 提示 trim
- **H8**：新会话验证常用项目命令仍可调用（如 `bash scripts/start_all.sh`、`npm run build` 等）

---

## 三、修改的所有文件清单

| 序号 | 路径 |
|------|------|
| 1 | `backend/app/services/tts_service.py` |
| 2 | `backend/app/services/asr_service.py` |
| 3 | `backend/requirements.txt` |
| 4 | `frontend/src/store/modules/tts.js` |
| 5 | `frontend/src/components/tts/TTSModelStatus.vue` |
| 6 | `frontend/src/views/TTSStudio.vue` |
| 7 | `scripts/precheck.sh` |
| 8 | `.claude/settings.local.json` |

---

## 四、未做事项与遗留中/低优先级

- **未执行**：测试 / 启动 / git commit（按用户协作规则）
- **遗留**：扫描报告中的 🟡 中优先级（M1–M12）与 🟢 低优先级（L1–L7）未处理，下次会话可继续按编号挑选
- **未更新 CLAUDE.md**：本次改动未引入新的外部行为（idle-unload 默认值未变、API 契约未变），故不动 CLAUDE.md
