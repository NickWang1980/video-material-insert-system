# 工作流程蛇形布局 + 视频生产分组 — 计划

时间戳：2026-05-15
分支：feature/3.0-adding-tts-module

## 用户需求

1. 控制台 (`Home.vue`) 的「工作流程」UI，在「混剪」之前新增 3 个步骤：
   - ① 文案生成
   - ② 语音生成（跳转到现有 /tts）
   - ③ 视频生成
2. 整个流程蛇形布局，每行 4 个 box（共 9 步：第一行 1-4 →，第二行 5-8 ←，第三行 9 →）。
3. 左侧 navbar 在「控制台」下方新增对应模块子页。

## 方案

### 路由 / 页面

| 路径 | 页面 | 说明 |
| --- | --- | --- |
| `/copy-gen` | `CopyGen.vue`（新建） | 文案生成占位页（敬请期待） |
| `/voice-gen` | redirect → `/tts` | 与现有 TTS 复用 |
| `/video-gen` | `VideoGen.vue`（新建） | 视频生成占位页（敬请期待） |

### 侧栏分组

在 `Sidebar.vue` 的 `allItems` 中，于「控制台」和「混剪单元」之间插入新顶级分组：

```
视频生产
├── 文案生成   /copy-gen   short:文
├── 语音生成   /tts        short:语
└── 视频生成   /video-gen  short:视
```

`moduleKey` 沿用 `console`，确保所有具备控制台权限的用户均可见。

### 蛇形工作流程 UI（Home.vue）

9 步 box，顺序：
1. 文案生成 → 2. 语音生成 → 3. 视频生成 → 4. 混剪
   ↓
8. 新建任务 ← 7. 创建源视频条目 ← 6. 创建模板 ← 5. 上传素材
   ↓
9. 下载产物

用 3 个独立 flex 行：
- 行 1：`flex` 左→右，4 box + 3 内部箭头
- 中间下行箭头：放在最右列（视觉上）
- 行 2：`flex flex-row-reverse` 实现 5,6,7,8 从右到左（箭头方向 ←）
- 中间下行箭头：放在最左列
- 行 3：1 box + 后续箭头隐藏

每个 box 自带数字标号、标题、简短描述、跳转按钮。

## 交付物

1. `frontend/src/views/CopyGen.vue` （新建）
2. `frontend/src/views/VideoGen.vue` （新建）
3. `frontend/src/router/index.js`（新增 3 条路由）
4. `frontend/src/components/layout/Sidebar.vue`（新增「视频生产」分组）
5. `frontend/src/views/Home.vue`（工作流程改 9 步蛇形）
6. `docs/20260515_workflow_snake_layout_plan.md` (本文件)
7. `docs/20260515_workflow_snake_layout_changelog.md`
8. `CLAUDE.md`（同步工作流和侧栏说明）

## 重启 / 构建影响

- 后端：**无需重启**（无 Python 改动）。
- 前端：dev 模式 Vite 热更新即可；prod 模式需要重新 `npm run build`。
- 数据库：无需迁移。
- 依赖：无需重装。
