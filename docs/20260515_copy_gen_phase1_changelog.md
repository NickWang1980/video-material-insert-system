# 文案生成 (Copy Gen) Phase-1 移植 — Changelog

时间戳：2026-05-15
分支：feature/3.0-adding-tts-module
计划：`C:\Users\techm\.claude\plans\quiet-bouncing-squid.md`

## 概述

把 `D:\workspace\bzybox\v-project\bzyagent\` 的口播文案生成系统（Flask + 原生 HTML，约 4000 行 Python + 600 行 HTML）按 Phase-1 范围移植到本项目，作为「视频生产 → 文案生成」模块。UI/UX 完全对齐主项目的 Vue 3 + Element Plus + Tailwind 风格，参考 `TTSStudio.vue` 的多 tab + 双栏 + 历史侧栏 + 折叠面板模式。后端走 FastAPI + SQLAlchemy + 加密的 ModelConfig 持久化；前端控制台首页蛇形流程图中 ①文案生成 → ②语音生成 现在可串联。

## Phase-1 范围（已实现）

- **快速生成**：主题 + 平台 + 字数范围 + 版本数 + 模板/脚本类型 → 多版本文案 + Qwen3-TTS 格式输出
- **模型配置 CRUD**：多 OpenAI-compatible 配置并存，api_key 在库中 Fernet 加密；含「测试连通性」按钮
- **Agent 系统**：Agent CRUD + 规则 CRUD + 知识库 CRUD + 用 Agent 生成
- **生成历史**：本地 localStorage 50 条 + 后端 SQLite `copy_gen_history` 分页
- **一键送 TTS**：结果卡上的按钮把 Qwen3-TTS 格式按行拆解后调用现有 `/api/tts/synthesize`
- **i18n**：zh-CN / en-US 同 372 leaf key，结构对齐

## 范围外（留待后续）

- 文档上传 → LLM 抽取规则
- 从优秀文案样例学习 → LLM 建议规则
- 整合优化（rules merge）
- 多用户隔离 Agent（本期所有 Agent 全局可见）
- 协作 / 导出
- 历史行的 user_id 关联（当前写入 `None`）
- Qwen 模型 `extra_body={"thinking":{"type":"disabled"}}` 选项

## 文件清单

### 后端 — 新建 10 个（约 2319 LOC）

| 文件 | 用途 |
| --- | --- |
| `backend/app/models/copy_gen.py` | 5 个 SQLAlchemy 模型：`CopyGenModelConfig`、`CopyGenAgent`、`CopyGenRule`、`CopyGenKnowledge`、`CopyGenHistory` |
| `backend/app/schemas/copy_gen.py` | Pydantic v2 全套 request / response：`ModelConfigCreate/Out/Update`、`AgentCreate/Detail/Summary/Update`、`RuleCreate/Out/Update`、`KnowledgeCreate/Out/Update`、`GenerateRequest/Response`、`VersionOut`、`HistoryOut`、`EnumsResponse` |
| `backend/app/api/copy_gen.py` | `APIRouter(prefix="/api/copy-gen")`，覆盖 20+ 端点（generate / models / agents / rules / knowledge / history / enums） |
| `backend/app/services/copy_gen/__init__.py` | 包标记 |
| `backend/app/services/copy_gen/templates.py` | 10 个文案模板 + 平台 tone + 情绪 / 速度 / 脚本类型 / 规则 / 知识枚举（自 bzyagent `src/templates.py` 逐字移植） |
| `backend/app/services/copy_gen/voice_config.py` | `VoiceConfig` + `parse` + `parse_lines`（Qwen3-TTS `content\|emotion\|speed` 解析） |
| `backend/app/services/copy_gen/llm_client.py` | `openai>=1.0` SDK 薄封装；按 `ModelConfig` 注入 `base_url` / `api_key`；超时来自 `settings.copy_gen_timeout` |
| `backend/app/services/copy_gen/model_config_service.py` | CRUD + Fernet 加解密 + `test_connectivity` |
| `backend/app/services/copy_gen/agent_service.py` | Agent + Rule + Knowledge CRUD + `build_system_prompt`（按优先级排序规则 + 拼接知识 + 12000 字符截断） |
| `backend/app/services/copy_gen/generator_service.py` | quick + agent 生成入口；顺序 N 版本；产物写入 `copy_gen_history` |

### 后端 — 修改 6 个

| 文件 | 改动 |
| --- | --- |
| `backend/main.py` | line 21 `from .app.api.copy_gen import router as copy_gen_router`，line 80 `app.include_router(copy_gen_router)` |
| `backend/app/models/database.py` | `init_db()` 内追加 5 个 copy_gen 模型 import，`Base.metadata.create_all` 自动建表 |
| `backend/app/schemas/role.py` | `ALL_MODULE_KEYS` + `DEFAULT_USER_MODULE_KEYS` 加入 `"copy_gen"` |
| `backend/app/config.py` | 新增 4 个 Settings 字段：`copy_gen_default_base_url` / `copy_gen_default_model` / `copy_gen_timeout` / `copy_gen_llm_key` |
| `backend/requirements.txt` | 追加 `openai>=1.0.0,<2.0` 与 `cryptography>=42.0.0` |
| `backend/.env.example` | 追加「文案生成 (Copy Gen)」段（COPY_GEN_LLM_KEY / COPY_GEN_DEFAULT_BASE_URL / COPY_GEN_DEFAULT_MODEL / COPY_GEN_TIMEOUT） |

### 前端 — 新建 14 个（约 3940 LOC）

| 文件 | 用途 |
| --- | --- |
| `frontend/src/api/copyGen.js` | Axios 封装，19 个端点函数；`generate` / `generateWithAgent` 用 180s 超时 + AbortController |
| `frontend/src/store/modules/copyGen.js` | Pinia store id `"copyGen"`，照搬 `tts.js` 模式；localStorage key `vmis_copygen_history`（≤50 条 + 配额超限 trim） |
| `frontend/src/locale/zh-CN/copyGen.json` | 372 leaf keys 中文 |
| `frontend/src/locale/en-US/copyGen.json` | 372 leaf keys 英文（与中文同结构） |
| `frontend/src/views/CopyGen.vue` | 顶级页面：header + 状态条 + 4 tab（快速生成 / Agent / 模型 / 历史） |
| `frontend/src/components/copyGen/QuickGenerator.vue` | 表单 + 结果区 + 右侧摘要 + 折叠历史 |
| `frontend/src/components/copyGen/AgentManager.vue` | Agent 列表 + 选中显示详情 |
| `frontend/src/components/copyGen/AgentDetail.vue` | 基础信息表单 + 规则 / 知识 tab |
| `frontend/src/components/copyGen/RuleEditor.vue` | 规则表 + 行内编辑 + 新建对话框 |
| `frontend/src/components/copyGen/KnowledgeEditor.vue` | 知识表 + 行内编辑 + 新建对话框 |
| `frontend/src/components/copyGen/ModelConfigManager.vue` | 模型配置表 + 编辑对话框 + 测试按钮 |
| `frontend/src/components/copyGen/ResultCard.vue` | 单版本结果卡：复制纯文本 / 复制 TTS 格式 / 查看 prompt / 送 TTS |
| `frontend/src/components/copyGen/SendToTTSDialog.vue` | 选行 + 音色模式 + 逐行调 `/api/tts/synthesize` |
| `frontend/src/components/copyGen/HistoryList.vue` | 本地 / 服务端历史双 tab |

### 前端 — 修改 2 个

| 文件 | 改动 |
| --- | --- |
| `frontend/src/locale/index.js` | 注册 `copyGen` 命名空间（zh-CN + en-US） |
| `frontend/src/components/layout/Sidebar.vue` | 「文案生成」子项的 `moduleKey` 由 `console` 改为 `copy_gen`（其他子项未动） |

### 文档 — 新建

- `docs/20260515_copy_gen_phase1_plan.md`（即计划文件 `C:\Users\techm\.claude\plans\quiet-bouncing-squid.md` 的本地映射；下次提交前可考虑拷贝到 docs 下作为版本化记录）
- `docs/20260515_copy_gen_phase1_changelog.md`（本文件）

## 数据库变更

5 张新表（首次启动 `init_db` 时由 SQLAlchemy `Base.metadata.create_all` 自动建立）：

```
copy_gen_model_configs (id, name, model_name, base_url, api_key_enc, temperature, max_tokens, system_prompt, created_at, updated_at)
copy_gen_agents (id, name, description, platform, industry, default_template, default_target_words, default_tolerance, default_script_type, model_config_id FK, is_active, created_at, updated_at)
copy_gen_rules (id, agent_id FK, category, content, original_content, rule_type, priority, source, created_at, updated_at)
copy_gen_knowledge (id, agent_id FK, category, title, content, status, status_note, created_at)
copy_gen_history (id, agent_id?, model_config_id, payload_json, results_json, user_id?, created_at)
```

无需手工 ALTER；`_ensure_schema_compatibility()` 未触及，新表走标准 metadata create_all。

## 权限

`schemas/role.py` 把 `"copy_gen"` 加入 `ALL_MODULE_KEYS` 与 `DEFAULT_USER_MODULE_KEYS`，意味着：

- 管理员默认可见
- 普通用户默认可见
- 「视频生产 → 文案生成」侧栏入口走 `moduleKey: "copy_gen"`
- `database.py` 的 `_ensure_default_roles()` 会把新 key 合并进现有角色的 `module_keys`，无需手动迁移

## 关键决策

- **Fernet key 兜底**：`copy_gen_llm_key` 环境变量 → `data/.copy_gen_key` 文件 → 自动生成（首次启动写入并 INFO 日志提示备份）。Fernet key 丢失等同所有 model_config 的 api_key 不可用，但 ModelConfig 记录仍在 — 用户只需重新填 api_key 即可恢复。
- **生成顺序而非并发**：N 个版本顺序调 LLM。Phase-1 简单优先，后续如需提速可改 `asyncio.gather` 并发。
- **Agent prompt 长度**：`build_system_prompt` 在 12000 字符处截断并 WARNING 日志。下期可加 LLM 总结化。
- **历史的 user_id**：当前写 `None`；多用户隔离留作 Phase-2。
- **送 TTS 协议**：客户端在 `SendToTTSDialog` 中按行循环调现有 `POST /api/tts/synthesize`，每行 `text=content`，`instruct=<emotion>, <speed>` 拼装。无新增后端端点。
- **Locale 重整**：sub-agent C 实际使用的 key 比 sub-agent B 写 locale 时的契约更细，由一轮专门的 locale 校对补全到 372 leaf key，并保留 sub-agent B 写的旧 nested 结构作为兼容。

## 重启 / 构建 / 依赖

- **后端**：必须重启 uvicorn（新路由 + 新模型）。首次启动会：
  - 自动建 5 张新表
  - 自动把 `copy_gen` 模块权限合并到 `admin` / `user` 角色
  - 如 `COPY_GEN_LLM_KEY` 缺失，自动生成 Fernet key 并写入 `data/.copy_gen_key`（请备份）
- **前端**：dev 模式 Vite 热更新；prod 模式需 `cd frontend && npm run build`
- **依赖（必须重装）**：
  - 后端：`pip install -r backend/requirements.txt`（新增 `openai>=1.0,<2.0` 与 `cryptography>=42.0.0`）
  - 前端：无新依赖
- **数据库迁移**：无需手动迁移；create_all 自动处理

## 启动命令

```bash
# 后端
cd backend
pip install -r requirements.txt    # 一次性，安装 openai + cryptography
cp .env.example .env               # 如尚未存在；按需配 COPY_GEN_DEFAULT_BASE_URL / COPY_GEN_DEFAULT_MODEL
cd ..
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# 前端 dev（推荐验收）
cd frontend
npm run dev                        # http://localhost:5173

# 前端 prod
cd frontend
npm run build                      # 输出到 frontend/dist/

# 全栈一键
scripts/start_all.bat              # Windows dev
scripts/start_all.bat --prod       # Windows prod
```

## 验收 checklist（建议人工跑一遍）

1. 启动后端，控制台日志应出现自动建表 / Fernet key 生成提示
2. 浏览器登录后侧栏「视频生产 → 文案生成」可点击进入
3. 切到「模型配置」tab，新增一条（OpenAI 兼容端点）→ 点「测试连通性」返回 success
4. 切到「快速生成」，主题 = 「免费听音乐的方法」，平台 = 抖音，模板 = product_scenario，版本数 = 2，点击「生成文案」
5. 看到 2 张 ResultCard，每张包含 Qwen3-TTS 多行
6. 点结果卡「送 TTS」→ 选行 → 选预设 voice → 开始合成 → 链接「去 TTS 工作台」可跳 `/tts`
7. 切到「Agent 管理」，新建一个 Agent → 加 2 条规则 + 2 条知识 → 在快速生成中选中该 Agent → 重新生成 → 系统提示词中含规则
8. 刷新页面，历史 tab 中「本地」侧仍有最近记录；「服务端」侧分页加载
9. 切语言（页面右上角 EN/中按钮）→ 全部文案切换；无空白 / key 字符串残留

## 风险点

- LLM 调用是网络密集 + 不可重现：单次生成 30–90 秒，多版本时长线性叠加；前端用 AbortController 已支持取消
- Fernet key 持久化在 `data/.copy_gen_key`（容器化部署需注意持久卷映射）
- bzyagent 是中文 prompt：移植后保留中文 system prompt，UI 通过 i18n 切英文
- Agent prompt 长度爆 token：12000 字符截断兜底，对高级 Agent 不够时需观察日志

## Token 估算（本轮）

- input（读）：约 ~110K tokens（项目结构扫描 + bzyagent 关键文件参考 + 三个 sub-agent 总结回传）
- output（写）：约 ~25K tokens（本主代理产生的协调消息 + 文档；3 个 sub-agent 自有 token 计入它们自身的 usage：A 135K、B 64K、C 106K、locale agent 67K — 详见各 agent 用量回传）

任务完成。
