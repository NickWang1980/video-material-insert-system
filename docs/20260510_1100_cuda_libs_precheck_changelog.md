# 20260510_1100 CUDA 运行时库预检 — 变更说明

> 范围：`scripts/precheck.sh` 新增第 4.5 段；`CLAUDE.md` TTS lazy-loading 段补充一行 precheck 行为说明。
> 触发：用户在 Settings 选 `large-v3-turbo` + `float16` 后，ASR 报 `Library cublas64_12.dll is not found or cannot be loaded`，且声明本机"没有 CUDA"。RCA 见前一轮对话与 `docs/20260507_1731_cuda_mode_audit.md`。
> 目的：在启动期把 ASR/TTS 共同依赖的 CUDA 12 运行时 DLL 探测一遍，把"驱动在但 toolkit / cuDNN 没装齐"这类假阳性提前暴露，给出明确指引。

---

## 一、改动清单

| 文件 | 改动类型 | 行数变化 | 说明 |
|---|---|---|---|
| `scripts/precheck.sh` | 新增段（第 4.5） | +120 / -0 | 新增 `check_cuda_runtime_libs()` 函数 + 调用 |
| `CLAUDE.md` | 微调 | +2 / -0 | TTS lazy-loading 段补一行 precheck CUDA 行为 |
| `docs/20260510_1100_cuda_libs_precheck_changelog.md` | 新增 | +若干 | 本文件 |

---

## 二、precheck.sh 第 4.5 段做了什么

### 2.1 触发条件

```bash
command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1
```

- `nvidia-smi` 不存在或运行失败 → 视为无 NVIDIA 驱动 → 直接 `log_ok` 通过（CPU 模式正常）。
- `nvidia-smi` 能跑 → 进入 DLL 探测。

### 2.2 探测策略

Python 子进程内：

1. 先 `import ctranslate2`——CTranslate2 4.x 在 import 时会调 `os.add_dll_directory()`，把 pip 包 `nvidia-cublas-cu12` / `nvidia-cudnn-cu12` 内的 DLL 目录注册到搜索路径。这样 ctypes 才能探到 pip 安装的 DLL，而不是只看系统 PATH。
2. 用 `ctypes.WinDLL` / `ctypes.CDLL` 试加载下列 DLL，每个加载成功即 `[OK]`，失败为 `[MISS]`：

| 类别 | Windows | Linux | 来源 |
|---|---|---|---|
| 必需 | `cudart64_12.dll` | `libcudart.so.12` | CUDA 12 Runtime |
| 必需 | `cublas64_12.dll` | `libcublas.so.12` | cuBLAS 12（用户当前报错的就是它） |
| 必需 | `cublasLt64_12.dll` | `libcublasLt.so.12` | cuBLAS LT 12 |
| 必需（任一） | `cudnn64_9.dll` / `cudnn_ops64_9.dll` / `cudnn_ops_infer64_8.dll` / `cudnn_cnn_infer64_8.dll` | 对应 .so | cuDNN 8 或 9 任一 |

3. 附带打印 `ctranslate2.get_cuda_device_count()` 与 `torch.cuda.is_available() / torch.version.cuda`——让用户一次性看清楚"上层服务以为有没有 CUDA"。
4. 任一必需项 MISS 则 Python 退出码 1，bash 据此 `log_warn` + 给出三种解决方向。

### 2.3 三种解决方向（按推荐度）

| 选项 | 操作 | 适合谁 |
|---|---|---|
| A | UI Settings → ASR Compute Type 改 `int8` | 不想配 CUDA 环境，只要能跑就行 |
| B | `pip install nvidia-cublas-cu12 nvidia-cudnn-cu12 --extra-index-url https://pypi.nvidia.com` | 想 GPU 加速、又不想动系统级 toolkit |
| C | 安装 NVIDIA CUDA Toolkit 12.x + cuDNN 8/9，并重启 shell | 全套官方安装，长期维护 |

---

## 三、对启动流程的影响

- **预检不会失败阻断启动**：DLL 缺失只 `log_warn`，不会 `log_fail`。这是有意的——很多用户就想跑 CPU 模式（`int8`），他们不需要 CUDA 库。
- **新增 stdout**：当探测到 NVIDIA 驱动时，会多打印 5–8 行 DLL 状态，让用户一眼看清现状。
- **耗时**：约 +0.5–1.5 秒（一次 Python 启动 + ctranslate2/torch import + 几次 ctypes 调用）。无 NVIDIA 驱动时几乎零耗时（仅一次 `nvidia-smi` 探测）。
- **不改运行时行为**：`asr_service._resolve_device_compute()` 与 `tts_service._detect_device_dtype()` 都没动——precheck 只做提醒，不修判定。这与上一份 audit 文档（`20260507_1731_cuda_mode_audit.md`）建议的 P0 改造是分开的，本次只补预检入口。

---

## 四、用户后续操作

### 4.1 重启 / rebuild 矩阵

| 项 | 是否需要 |
|---|---|
| 后端 uvicorn 重启 | **不需要**（precheck 是启动前脚本，不进 uvicorn 进程） |
| 前端 npm run build | **不需要**（无前端改动） |
| 数据库迁移 | **不需要** |
| 重新安装依赖 | **不需要**（不新增 Python 包；如果要走方向 B，那是用户自己装） |

### 4.2 验证命令

```bash
# 直接跑 precheck（不启服务）
./scripts/precheck.sh

# 或者完整启动（precheck 是 start_all.sh 的第一步）
./scripts/start_all.bat       # Windows 一键
./scripts/start_all.sh        # Linux/Mac
```

预期输出（无 NVIDIA 驱动机器）：
```
[precheck] ✅  CUDA 运行时 — 未检测到 NVIDIA 驱动（ASR/TTS 自动走 CPU，正常）
```

预期输出（有驱动 + CUDA 12 + cuDNN 装齐）：
```
[precheck]      检测到 NVIDIA 驱动 — 探测 CUDA 12 运行时 DLL...
[precheck]      [OK  ] cudart64_12.dll  (CUDA Runtime 12)
[precheck]      [OK  ] cublas64_12.dll  (cuBLAS 12)
[precheck]      [OK  ] cublasLt64_12.dll  (cuBLAS LT 12)
[precheck]      [OK  ] cudnn64_9.dll  (cuDNN 9 主入口) — cuDNN 任一即满足
[precheck]      ct2.get_cuda_device_count() = 1
[precheck]      torch.cuda.is_available() = True  (torch.version.cuda=12.1)
[precheck] ✅  CUDA 运行时库 — 必需 DLL 齐全（cudart / cuBLAS / cuBLASLt / cuDNN）
```

预期输出（用户当前情形：有驱动但缺 cuBLAS）：
```
[precheck]      检测到 NVIDIA 驱动 — 探测 CUDA 12 运行时 DLL...
[precheck]      [MISS] cudart64_12.dll  (CUDA Runtime 12)
[precheck]      [MISS] cublas64_12.dll  (cuBLAS 12)
[precheck]      [MISS] cublasLt64_12.dll  (cuBLAS LT 12)
[precheck]      [MISS] cuDNN —— 未探测到 cudnn64_9.dll / cudnn_ops64_9.dll / cudnn_ops_infer64_8.dll / cudnn_cnn_infer64_8.dll
[precheck]      ct2.get_cuda_device_count() = 1
[precheck]      torch.cuda.is_available() = False  (torch.version.cuda=None)
[precheck] ⚠️   CUDA 运行时库 — 部分 DLL 缺失 → ASR float16/float32 与 TTS GPU 模式都会失败
[precheck]      上方 [MISS] 是缺失项；常见根因：装了 NVIDIA 驱动但未装 CUDA 12 Toolkit + cuDNN
[precheck]      解决三选一（按推荐度从高到低）：
[precheck]        A. UI Settings → ASR Compute Type 选 int8（强制 CPU，绕过 CUDA，最稳）
[precheck]        B. pip install nvidia-cublas-cu12 nvidia-cudnn-cu12 --extra-index-url https://pypi.nvidia.com
[precheck]           （pip 路径下的 DLL 由 ctranslate2 import 时自动注册，多数情况无需手动改 PATH）
[precheck]        C. 装 NVIDIA CUDA Toolkit 12.x + cuDNN 8 或 9，重启 shell 后再 ./scripts/start_all.sh
```

---

## 五、未做的事（明确边界）

- **没改** `_resolve_device_compute()` 的判定逻辑（仍然是"有 ct2 device → 用 CUDA"，未来用户即便选 float16 还是会触发 CUDA 路径再炸）。
- **没改** `_detect_cuda_available()`（依然只看 device count，没加 DLL 试探）。
- **没动** `tts_service.py`、`Settings.vue`、`config.py`。
- **没新增** Python 包到 `requirements.txt`。

如果要让"运行时也强壮"——即便用户硬选 float16 也能在 DLL 缺失时优雅回退 CPU——需要改 `asr_service.py:_detect_cuda_available()` 加一层 ctypes 试探。这是另一份工作，待你拍板再做。

---

## 六、Token 估算

- input（读）：precheck.sh 684 行 + asr_service.py 480 行 + 既有 cuda_mode_audit md + start_all.bat + grep 命中 ≈ **~14,000 tokens**
- output（写）：precheck.sh 新增 +120 行 + 本 changelog md + CLAUDE.md 微调 ≈ **~3,400 tokens**
