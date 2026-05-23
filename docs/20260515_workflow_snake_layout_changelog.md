# 工作流程蛇形布局 + 视频生产分组 — Changelog

时间戳：2026-05-15
分支：feature/3.0-adding-tts-module

## 改动概览

控制台 (`Home.vue`) 的「工作流程」UI 由 6 步线性扩展为 9 步蛇形（每行 4 box，行向 → ← →）；左侧 navbar 在「控制台」与「混剪单元」之间新增顶级分组「视频生产」，包含 3 个子页：文案生成 / 语音生成 / 视频生成。语音生成复用现有 `/tts`；文案生成、视频生成本轮为占位页面（敬请期待）。

## 文件清单

### 新增

| 文件 | 用途 |
| --- | --- |
| `frontend/src/views/CopyGen.vue` | 文案生成占位页（路由 `/copy-gen`） |
| `frontend/src/views/VideoGen.vue` | 视频生成占位页（路由 `/video-gen`） |
| `docs/20260515_workflow_snake_layout_plan.md` | 本轮变更计划 |
| `docs/20260515_workflow_snake_layout_changelog.md` | 本文件 |

### 修改

| 文件 | 改动 |
| --- | --- |
| `frontend/src/router/index.js` | 引入 `CopyGen`、`VideoGen`；新增 `/copy-gen`、`/video-gen` 路由 + `/voice-gen` redirect → `/tts` |
| `frontend/src/components/layout/Sidebar.vue` | 在 `allItems` 中「控制台」与「混剪单元」之间插入「视频生产」分组（含 3 子项：文案生成 → `/copy-gen`、语音生成 → `/tts`、视频生成 → `/video-gen`）；分组展开状态默认 true 并持久化 |
| `frontend/src/views/Home.vue` | 工作流程从 6 步线性改为 9 步蛇形 grid 布局：第一行 ①→②→③→④（文案→语音→视频→混剪），第二行 ⑧←⑦←⑥←⑤（任务←源视频←模板←素材），第三行 ⑨（下载产物）；新增 `.flow-row`、`.flow-connector`、`.flow-down`、`.flow-spacer` 样式；同步 dark / glass 主题颜色 |
| `CLAUDE.md` | 在「核心流程」与「Common Change Patterns」处同步「视频生产」分组与蛇形工作流入口说明 |

## UI 结构说明

- **蛇形 grid**：`grid-template-columns: 1fr auto 1fr auto 1fr auto 1fr`（4 box + 3 arrow 槽位）。
- **行间连接**：转向行 `.flow-connector` 采用 4 等宽列，分别在最右 / 最左放置 `↓` 大箭头，视觉上承接每行末端的 box。
- **窄屏自适应**：`max-width: 1024px` 时退化为单列，箭头与 connector 隐藏。
- **侧栏分组**：「视频生产」默认展开；moduleKey 沿用 `console`，与控制台同权限。

## 重启 / 构建影响

- 后端：**无需重启**（无 Python 改动）。
- 前端：
  - dev 模式：Vite 热更新自动生效，无需手工操作。
  - prod 模式：需重新 `cd frontend && npm run build`。
- 数据库：无需迁移。
- 依赖：无需重装。

## 编译 / 启动命令

```bash
# 前端 dev（推荐验收）
cd frontend
npm run dev          # http://localhost:5173

# 前端 prod 构建
cd frontend
npm install          # 如依赖未装
npm run build        # 输出到 frontend/dist/

# 全栈
scripts/start_all.bat              # dev
scripts/start_all.bat --prod       # prod（FastAPI 挂载 frontend/dist）
```

## 后续

- 文案生成 / 视频生成的后端服务与业务页面待后续模块独立交付。
- 「视频生产」分组的子项可在未来按需要加 `moduleKey`/`adminOnly` 做权限收口。
