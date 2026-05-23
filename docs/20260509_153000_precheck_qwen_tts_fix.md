# 20260509_153000_precheck_qwen_tts_fix.md

## 问题描述

`precheck.sh` 在检查 qwen_tts 模型状态时存在以下问题：

### 问题 1：TTS 模型缓存检测逻辑在 Windows Git Bash 下可能失败

原代码使用 `ls "${snap%/}"/*.safetensors` 在 Windows Git Bash 环境下处理含空格的路径时会失败，导致即使模型已缓存也可能检测不到。

**位置**：`scripts/precheck.sh` 第 595-609 行 `_tts_model_cached()` 函数

### 问题 2：ASR 模型下载无进度条

ASR 模型下载（medium 约 1.5GB）时没有任何进度提示，用户不知道下载进度。

**位置**：`scripts/precheck.sh` 第 500-575 行 ASR 下载逻辑

### 问题 3：pip 安装依赖时可能因网络问题失败

pip 安装 Python 依赖时，默认源在中国大陆可能连接不稳定，导致 SSL 错误或超时，且没有自动重试机制。

**位置**：`scripts/precheck.sh` 第 312-332 行 Python 依赖安装逻辑

---

## 修复内容

### 修复 1：改进 `_tts_model_cached()` 函数

将 `ls` 命令替换为 `find`，更可靠地检测 `.safetensors` 和 `.bin` 文件：

```bash
# 旧代码
for snap in "${snap_base}"/*/; do
  [ -d "$snap" ] || continue
  if ls "${snap%/}"/*.safetensors >/dev/null 2>&1 || ls "${snap%/}"/*.bin >/dev/null 2>&1; then
    return 0
  fi
done

# 新代码
if [ -n "$(find "$snap_base" -maxdepth 2 -type f \( -name "*.safetensors" -o -name "*.bin" \) 2>/dev/null)" ]; then
  return 0
fi
```

### 修复 2：为 ASR 模型下载添加 tqdm 进度条

引入 `tqdm` 进度条库，通过 `huggingface_hub` 的 `progress_callback` 显示下载进度：

```python
from tqdm import tqdm

class TqdmProgressCallback(tqdm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, unit='B', unit_scale=True,
                         bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]')

def _progress_callback(chunk_size, file_size, download_speed, **_):
    if file_size and file_size > 0:
        progress.total = file_size
        progress.update(chunk_size)

snapshot_download(repo_id=repo_id, local_dir=local_dir,
                  local_dir_use_symlinks=False,
                  progress_callback=_progress_callback)
```

### 修复 3：pip 安装依赖添加重试和镜像源切换机制

当默认 PyPI 源下载失败时，自动尝试国内镜像源：

```bash
_pip_install_with_retry() {
  local timeout=120
  
  # 默认源
  pip install -r requirements.txt --timeout "$timeout" -q && return 0
  
  # 清华镜像
  pip install -r requirements.txt --timeout "$timeout" -q \
    -i https://pypi.tuna.tsinghua.edu.cn/simple && return 0
  
  # 阿里云镜像
  pip install -r requirements.txt --timeout "$timeout" -q \
    -i https://mirrors.aliyun.com/pypi/simple && return 0
  
  return 1
}
```

### 修复 4：显示完整下载 URL

为每个下载操作显示完整的 URL 地址，方便用户了解下载来源和手动下载：

```bash
# FFmpeg 下载
log_dl "FFmpeg 未找到 — 从 ${url} 下载（约 100 MB）..."

# Python 依赖安装
log_info "requirements.txt 路径: $PROJECT_ROOT/backend/requirements.txt"
log_info "命令: pip install -r backend/requirements.txt --timeout ${timeout} -q"
log_info "镜像源: ${pypi_url}"

# ASR 模型下载
log_info "Hugging Face 仓库: https://huggingface.co/Systran/faster-whisper-${model}"
```

### 修复 6：完全移除 precheck.sh 中的 TTS 模块检查

从 precheck.sh 中删除了整个 TTS 模型检查部分，包括：
- `TTS_MODEL_REPOS` 数组定义
- `_tts_model_cached()` 函数
- TTS 模型状态检查循环

TTS 模型的下载和管理将完全由应用程序本身处理。

---

## 修改文件

| 文件 | 修改类型 | 说明 |
|------|----------|------|
| `scripts/precheck.sh` | 修改 | 修复 TTS 模型检测 + 添加 ASR 下载进度条 + pip 镜像源自动切换 + 显示完整下载 URL + qwen_tts 设为可选 + 移除 TTS 检查模块 |

---

## 验证方法

1. 运行 `bash scripts/precheck.sh` 确认无报错
2. 观察 ASR 模型下载时是否显示进度条
3. 模拟网络问题时，应自动切换到备用镜像源
4. 所有下载操作应显示完整的 URL 地址
5. precheck.sh 不应再显示任何 TTS 相关检查信息

---

## Token 消耗

- 读取：约 4,500 token
- 写入：约 2,500 token
- 搜索：约 2,000 token
- **总计约 9,000 token**
