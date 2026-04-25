# 亮色/暗色模式切换按钮

## 改动摘要

在 Header 右上角添加亮/暗模式切换按钮，支持 localStorage 持久化，页面刷新不闪烁。

## 涉及文件

| 文件 | 改动内容 |
|------|---------|
| `frontend/tailwind.config.js` | 添加 `darkMode: "class"` |
| `frontend/index.html` | 添加内联脚本，页面加载时立即应用 dark class，防止主题闪烁 |
| `frontend/src/assets/styles/global.css` | 添加 Element Plus CSS 变量暗色覆盖（bg/text/border/table/input/dialog 等），以及常用 Tailwind utility 暗色覆盖 |
| `frontend/src/App.vue` | 管理 `isDark` 状态，`onMounted` 时应用 class，传递 toggle 给 Header |
| `frontend/src/components/layout/Header.vue` | 右上角圆形图标按钮（月亮/太阳 SVG），接收 `isDark` prop |
| `frontend/src/components/layout/Sidebar.vue` | 全面添加 `dark:` Tailwind 变体；激活导航项暗色为白底黑字（反转设计） |
| `frontend/src/views/Home.vue` | 添加全局 `<style>` 块覆盖 scoped `.flow-step` 等暗色样式 |

## 暗色字体颜色设计

- 主文本：`#f3f4f6`（柔和偏白，非纯白，避免刺眼）
- 次级文本：`#d1d5db`
- 辅助/muted 文本：`#9ca3af`
- 卡片背景：`#1f2937`（gray-800）
- 页面背景：`#111827`（gray-900）
- 分割线/边框：`#374151`

## 是否需要重启

前端热更新自动生效（Vite dev server 下无需重启）。
