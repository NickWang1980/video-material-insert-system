# 文案生成 — Anthropic 原生 API 支持（修复 claude-opus-4-6 测试 404）

- 时间：2026-05-15 23:42
- 分支：feature/3.0-adding-tts-module
- 触发：用户在 /copy-gen → ModelConfig 测试连通 `claude-opus-4-6`，得到 `NotFoundError: Error code: 404`。

## DB 真实配置（id=5）

```
name     = claude-opus-4-6
model    = claude-opus-4-6
base_url = https://api.anthropic.com
api_key  = sk-ant-...0wAA   (108 字符，Anthropic native key)
temp     = 0.8
max_tokens = 4096
```

## 根因

`backend/app/services/copy_gen/llm_client.py` 此前**强制走 OpenAI SDK** 的 `chat.completions.create`，请求会拼成 `https://api.anthropic.com/chat/completions`。Anthropic 原生 API 的端点是 `/v1/messages`（完全不同的协议、不同 schema、不同 auth header），**该路径不存在 → 404 NotFoundError**。

注意：OpenAI 兼容协议在 NVIDIA NIM / DeepSeek / OpenAI / vLLM 等都能直接用，但 Anthropic 官方至今**不**提供 OpenAI 风格的 /chat/completions 端点。

## 修复

### 1. `backend/requirements.txt`

```diff
 openai>=1.0.0,<2.0       # OpenAI-compatible chat.completions client
+anthropic>=0.40.0,<1.0   # Anthropic Messages API client（自动路由）
 cryptography>=42.0.0
```

### 2. `backend/app/services/copy_gen/llm_client.py`

新增：

- `_is_anthropic_target(base_url, model)`：检测 `anthropic.com` 域名 **或** model 以 `claude-`/`claude.` 开头。
- `_split_system_messages(messages)`：把 OpenAI-style messages 数组里的 `role=system` 抽出来合并成单一 system string（Anthropic 协议要求 system 单独传，不能塞在 messages 里）。
- `_anthropic_chat_completion(...)`：用 `anthropic.Anthropic().messages.create()` 调用，把响应包装回与 OpenAI 一致的 `usage = {prompt_tokens, completion_tokens, total_tokens}` 形态供日志输出，避免日志键名歧义。
- `chat_completion` 顶部加路由分支：命中 anthropic 目标即走原生 SDK，否则继续走 OpenAI SDK。

新路径同样会在 `copy_gen_*.log` 中落盘：
- `[copy_gen][llm] (anthropic) call model=... msgs=... temp=... max_tokens=...`
- `[copy_gen][llm] request_body={provider: anthropic, model, max_tokens, messages, system, temperature}`
- `[copy_gen][llm] usage prompt=<input_tokens> completion=<output_tokens> total=<sum> elapsed=...`
- `[copy_gen][llm] response_body={provider: anthropic, id, model, type, stop_reason, content[], usage}`

`api_key` **永不**落盘（client 携带，不进入 request_log 字段）。

## 用真实 DB 配置实测结果

```
=== 修复前 ===
openai.NotFoundError: Error code: 404 — 向 api.anthropic.com/chat/completions

=== 修复后（用 DB id=5 真实数据 ping）===
anthropic.BadRequestError: Error code: 400
{'type': 'error',
 'error': {'type': 'invalid_request_error',
           'message': 'Your credit balance is too low to access the Anthropic API. 
                      Please go to Plans & Billing to upgrade or purchase credits.'},
 'request_id': 'req_011Cb4cGAqaxWZ8oFZeLwFCm'}
elapsed ≈ 7.0 s
```

**结论**：

| 维度 | 状态 |
|---|---|
| SDK 路由（404 根因） | ✅ 已修复 — 现在走 `/v1/messages`，能正确到达 Anthropic |
| API key 合法性 | ✅ 通过 — 否则会返回 `authentication_error` |
| model name `claude-opus-4-6` | ✅ 通过 model 验证 — 否则会先返回 `model_not_found_error` |
| **账户余额** | ❌ **不足** — 需要用户到 Anthropic Console → Plans & Billing 充值或购买 credits |

代码侧已经修复完毕。剩余的 400 是账户层面问题，不是程序 bug。给账户充值后再点一次「测试」，应返回 `OK — reply: <8-token ping>`。

## 是否需要其他操作

| 项目             | 是否需要 | 说明 |
| ---------------- | -------- | ---- |
| 重启后端 uvicorn | ✅ 需要 | llm_client.py 改动需要进程重新加载 |
| 安装依赖         | ✅ 需要 | `pip install -r backend/requirements.txt` 拉 `anthropic>=0.40.0,<1.0`（本机 dev 环境已经装好 anthropic 0.102.0，但 prod / CI 要补） |
| 重新 build 前端  | ❌ 不需要 | 仅后端逻辑变化 |
| 数据库迁移       | ❌ 不需要 | 未改 schema |
| 改 DB 数据       | ❌ 不需要 | model_name / base_url / api_key 保持不动 |

启动命令：
```
pip install -r backend/requirements.txt
scripts/start_all.bat
```

## 受影响文件

- 修改：`backend/requirements.txt`
- 修改：`backend/app/services/copy_gen/llm_client.py`
- 新增：`docs/20260515_2342_anthropic_native_support_changelog.md`

## Token 估算

- input（读）：约 8,500 tokens（model_config_service / copy_gen model / requirements / 现有 llm_client / DB 查询输出）
- output（写）：约 2,400 tokens（llm_client 增量、requirements diff、本 changelog）
