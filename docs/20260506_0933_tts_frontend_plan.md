# 20260506_0933 — TTS 模块前端集成计划（落档版）

## 背景

`feature/3.0-adding-tts-module` 分支后端 TTS 已就绪（FastAPI 9 路由 + Service + watchdog + tqdm 钩子），但 `frontend/src/` 内零 TTS 代码。本次工作把参考仓库 `D:\workspace\bzybox\v-project\Qwen3-TTS\` 的用户面向功能移植到主项目 Vue/Element Plus 单页应用。

## 范围（用户已确认 — A 必做 + 全部 B + 中英双语 + 并行 sub-agent）

### A. 核心 MVP
1. API 封装 `frontend/src/api/tts.js`
2. TTS Studio 主页面 `frontend/src/views/TTSStudio.vue`（双 Tab：声音克隆 / 预设音色）
3. 模型加载状态条 `frontend/src/components/tts/TTSModelStatus.vue`
4. Pinia store `frontend/src/store/modules/tts.js`
5. 路由 `/tts` + Sidebar 菜单项

### B. 选做（已勾选全部）
6. 历史记录（localStorage）
7. 批量合成（.txt → JSZip 客户端打包）
8. 独立播放器组件
9. TTS → 素材库联动

### C. i18n
10. 装 vue-i18n + 仅 TTS 模块 zh-CN / en-US 两套 locale
11. 顶部语言切换按钮（仅切 TTS 页面）

### D. 不做
- ❌ Gradio UI / Flask REST 重写 / start_all.ps1 移植 / CLI demo / 三语支持

## 文件清单

新建 13：
- `frontend/src/api/tts.js`
- `frontend/src/store/modules/tts.js`
- `frontend/src/views/TTSStudio.vue`
- `frontend/src/components/tts/TTSModelStatus.vue`
- `frontend/src/components/tts/TTSAudioPlayer.vue`
- `frontend/src/components/tts/TTSBatchPanel.vue`
- `frontend/src/components/tts/TTSHistoryList.vue`
- `frontend/src/components/tts/TTSReferenceUploader.vue`
- `frontend/src/components/tts/TTSPresetVoicePicker.vue`
- `frontend/src/locale/index.js`
- `frontend/src/locale/zh-CN/tts.json`
- `frontend/src/locale/en-US/tts.json`

修改 4：
- `frontend/package.json`（+ vue-i18n、jszip）
- `frontend/src/main.js`（注册 i18n）
- `frontend/src/router/index.js`（/tts 路由）
- `frontend/src/components/layout/Sidebar.vue`（菜单项）

## 并行拆分

```
Step 0/1 串行预备（i18n 骨架 + locale 文件）
   ↓
Step 2 并行 4 sub-agent
   Agent 1: tts.js + store/tts.js
   Agent 2: TTSStudio.vue 主页骨架
   Agent 3: TTSModelStatus + TTSReferenceUploader + TTSPresetVoicePicker
   Agent 4: TTSBatchPanel + TTSHistoryList + TTSAudioPlayer
   ↓
Step 3-6 串行收尾（接子组件、路由+菜单、素材联动、build+文档）
```

## 影响

- 重启后端：❌
- 重 build 前端：✅（必须 `npm install` 装 vue-i18n + jszip，再 `npm run build`）
- 数据库迁移：❌

## 验证（用户手动）

```
cd frontend
npm install
npm run dev    # http://localhost:5173 → 侧边栏 "TTS 合成"
```

走通：加载 Base → 文本输入 → 合成 → 试听；上传参考音频 → 克隆；启用 CustomVoice → 选 preset；批量 .txt → zip 下载；存为素材 → 跳素材库验证；中英切换。
