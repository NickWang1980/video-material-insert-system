# 20260509_154500_asr_model_reset_fix.md

## 问题描述

在设置页面选择 `large-v3-turbo` 作为 ASR 模型后，点击"保存"或"刷新"后，模型选择会被重置回 `small`。

### 根本原因

`backend/app/services/task_service.py` 中的 `ensure_settings_row()` 函数在每次调用时会检查 `asr_model` 是否在允许的列表中。如果模型不在 `{"small", "medium"}` 这两个值中，就会被重置为 `"small"`。

这导致 `large-v3` 和 `large-v3-turbo` 这两个有效模型每次访问设置时都被错误地重置。

**问题代码位置**：`backend/app/services/task_service.py` 第 358 行

```python
elif not row.asr_model or row.asr_model not in {"small", "medium"}:
    row.asr_model = "small"  # large-v3-turbo 会被错误重置为 small
```

---

## 修复内容

将 `ensure_settings_row()` 函数中的允许模型列表更新为包含所有有效的 ASR 模型：

```python
# 修复前
elif not row.asr_model or row.asr_model not in {"small", "medium"}:

# 修复后
elif not row.asr_model or row.asr_model not in {"small", "medium", "large-v3", "large-v3-turbo"}:
```

---

## 修改文件

| 文件 | 修改类型 | 说明 |
|------|----------|------|
| `backend/app/services/task_service.py` | 修改 | 更新 asr_model 允许列表，添加 large-v3 和 large-v3-turbo |
| `backend/app/services/rough_cut_service.py` | 修改 | `_get_system_asr_model()` 添加 large-v3 和 large-v3-turbo 到允许列表 |

---

## 额外修复：RoughCut ASR 任务

在 `task_service.py` 修复后，发现 `rough_cut_service.py` 中也有相同问题。

`_get_system_asr_model()` 函数同样只允许 `small` 和 `medium`，导致混剪项目的 ASR 任务也使用错误的模型。

```python
# 修复前
return model if model in {"small", "medium"} else "small"

# 修复后
return model if model in {"small", "medium", "large-v3", "large-v3-turbo"} else "small"
```

---

## 验证方法

1. 在设置页面选择 `large-v3-turbo` 模型
2. 点击"保存"按钮
3. 刷新页面
4. 确认模型选择仍然是 `large-v3-turbo` 而非被重置为 `small`
5. 创建混剪项目并上传素材，确认 ASR 使用 `large-v3-turbo` 模型

---

## Token 消耗

| 操作 | 消耗 |
|------|------|
| 搜索代码 | ~800 token |
| 读取文件 | ~500 token |
| 写入文档 | ~400 token |
| **总计** | **~1,700 token** |
