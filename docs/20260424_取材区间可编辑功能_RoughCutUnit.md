# 取材区间可编辑功能（RoughCutUnit.vue）

**日期：** 2026-04-24  
**分支：** feature/multi-roles-cut  
**涉及文件：** `frontend/src/views/RoughCutUnit.vue`

---

## 改动摘要

在「混剪单元」分镜卡片中，将只读的"取材 00:10.9 - 00:15.8"文本替换为可编辑的时间区间输入框，用户可在点击「保存本句」前手动调整取材起止时间，保存后后端通过 FFmpeg 按新区间重新裁剪角色视频。

---

## 具体改动

### 1. 新增 import
- 在 import 列表中加入 `regenerateRoughCutSentence`（已在 `api/roughCut.js` 中定义）

### 2. 新增响应式状态
- `sentenceEdits = reactive({})` — 按句子 ID 缓存用户编辑的 `{ sourceStart, sourceEnd }`

### 3. 新增辅助函数 `getSentenceEdit(sentenceId)`
- 按需懒初始化编辑状态：优先读取句子的 `sourceStartOverride/sourceEndOverride`，否则从 timeline clip 读取当前值
- 位置：紧跟 `sentenceClipText` 函数之后

### 4. 模板改动（分镜卡片时间区间区域）
- **旧：** 单行只读文本 `{{ sentenceClipText(sentence.id) }}`
- **新：** 两行布局
  - 第一行：标题文字 + 锁定时长开关（不变）
  - 第二行（仅当 clip 存在时显示）：两个 `el-input-number`（精度 0.1 秒，步进 0.1）分别绑定 `getSentenceEdit(sentence.id).sourceStart` 和 `.sourceEnd`，右侧附显时间线区间（只读）

### 5. `saveSentence` 函数更新
- 读取 `sentenceEdits[sentence.id]` 与当前 clip 对比，差值 > 0.05 秒即视为「有覆盖」
- 有覆盖时：在 payload 附加 `sourceStart / sourceEnd`，保存后追加调用 `regenerateRoughCutSentence` 重新生成 timeline clip，并清除该句子的本地编辑缓存（`delete sentenceEdits[sentence.id]`）
- 无覆盖时：行为与原来完全一致

---

## 数据流

```
用户修改输入框
  → getSentenceEdit(id).sourceStart/sourceEnd 更新
  → 点击「保存本句」
  → PATCH /api/rough-cut/projects/{id}/sentences/{sentenceId}
      payload: { estimatedDuration, locked, sourceStart, sourceEnd }
  → 后端存入 sourceStartOverride/sourceEndOverride
  → POST /api/rough-cut/projects/{id}/regenerate-sentence/{sentenceId}
  → 后端 build_project_timeline() 使用覆盖值
  → FFmpeg: -ss {sourceStart} -to {sourceEnd} -i {角色视频}
```

---

## 是否需要重启/build

- **后端：** 无需重启（后端代码未改动，API 已支持 sourceStart/sourceEnd）  
- **前端：** 热更新自动生效（开发模式）；生产环境需重新 `npm run build`
