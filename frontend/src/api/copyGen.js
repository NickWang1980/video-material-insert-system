import { api } from "./index";

// 文案生成 (Copy Gen) Axios 包装层 — 与后端 /api/copy-gen 契约一致。
// 生成类接口 (generate / generateWithAgent) 单独抬高 timeout 至 3 分钟，
// 因为 LLM 调用受网络与多版本顺序生成影响，30s 默认值常常不够；
// 调用方可传 { signal } 用于 AbortController 中止。

// ──────────────────────────────────────────────────────────────────────────
// Enums
// ──────────────────────────────────────────────────────────────────────────

export async function getEnums() {
  const { data } = await api.get("/copy-gen/enums");
  return data;
}

// ──────────────────────────────────────────────────────────────────────────
// Model Configs
// ──────────────────────────────────────────────────────────────────────────

export async function listModelConfigs() {
  const { data } = await api.get("/copy-gen/models");
  return data;
}

export async function createModelConfig(payload) {
  const { data } = await api.post("/copy-gen/models", payload);
  return data;
}

export async function updateModelConfig(id, patch) {
  const { data } = await api.put(`/copy-gen/models/${id}`, patch);
  return data;
}

export async function deleteModelConfig(id) {
  const { data } = await api.delete(`/copy-gen/models/${id}`);
  return data;
}

export async function testModelConfig(id) {
  // 后端会真正发起一次 LLM 请求做连通性测试，可能耗时较长。
  const { data } = await api.post(`/copy-gen/models/${id}/test`, null, {
    timeout: 60000,
  });
  return data;
}

// ──────────────────────────────────────────────────────────────────────────
// Agents
// ──────────────────────────────────────────────────────────────────────────

export async function listAgents() {
  const { data } = await api.get("/copy-gen/agents");
  return data;
}

export async function getAgentDetail(id) {
  const { data } = await api.get(`/copy-gen/agents/${id}`);
  return data;
}

export async function createAgent(payload) {
  const { data } = await api.post("/copy-gen/agents", payload);
  return data;
}

export async function updateAgent(id, patch) {
  const { data } = await api.put(`/copy-gen/agents/${id}`, patch);
  return data;
}

export async function deleteAgent(id) {
  const { data } = await api.delete(`/copy-gen/agents/${id}`);
  return data;
}

// ──────────────────────────────────────────────────────────────────────────
// Rules (agent-scoped)
// ──────────────────────────────────────────────────────────────────────────

export async function createRule(agentId, payload) {
  const { data } = await api.post(`/copy-gen/agents/${agentId}/rules`, payload);
  return data;
}

export async function updateRule(agentId, ruleId, patch) {
  const { data } = await api.put(
    `/copy-gen/agents/${agentId}/rules/${ruleId}`,
    patch
  );
  return data;
}

export async function deleteRule(agentId, ruleId) {
  const { data } = await api.delete(
    `/copy-gen/agents/${agentId}/rules/${ruleId}`
  );
  return data;
}

// ──────────────────────────────────────────────────────────────────────────
// Knowledge (agent-scoped)
// ──────────────────────────────────────────────────────────────────────────

export async function createKnowledge(agentId, payload) {
  const { data } = await api.post(
    `/copy-gen/agents/${agentId}/knowledge`,
    payload
  );
  return data;
}

export async function updateKnowledge(agentId, kid, patch) {
  const { data } = await api.put(
    `/copy-gen/agents/${agentId}/knowledge/${kid}`,
    patch
  );
  return data;
}

export async function deleteKnowledge(agentId, kid) {
  const { data } = await api.delete(
    `/copy-gen/agents/${agentId}/knowledge/${kid}`
  );
  return data;
}

// ──────────────────────────────────────────────────────────────────────────
// Generation
// ──────────────────────────────────────────────────────────────────────────

export async function generate(payload, options = {}) {
  // 多版本 LLM 串行调用通常 30–120 秒；30s 默认 timeout 常不够 —— 抬到 3 分钟。
  // 调用方可传 { signal } 用于 AbortController 中止。
  const { data } = await api.post("/copy-gen/generate", payload, {
    timeout: 180000,
    signal: options.signal,
  });
  return data;
}

export async function generateWithAgent(agentId, payload, options = {}) {
  const { data } = await api.post(
    `/copy-gen/agents/${agentId}/generate`,
    payload,
    {
      timeout: 180000,
      signal: options.signal,
    }
  );
  return data;
}

// ──────────────────────────────────────────────────────────────────────────
// History (server-side)
// ──────────────────────────────────────────────────────────────────────────

export async function listHistory({ limit = 20, offset = 0 } = {}) {
  const { data } = await api.get("/copy-gen/history", {
    params: { limit, offset },
  });
  return data;
}

export async function deleteHistory(id) {
  const { data } = await api.delete(`/copy-gen/history/${id}`);
  return data;
}
