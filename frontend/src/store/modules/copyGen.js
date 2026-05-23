import { defineStore } from "pinia";
import * as copyGenApi from "../../api/copyGen";
import { setLocale as _setLocale } from "../../locale";

const HISTORY_KEY = "vmis_copygen_history";
const HISTORY_MAX = 50;

export const useCopyGenStore = defineStore("copyGen", {
  state: () => ({
    // 后端 /enums 接口聚合返回；fetchEnums 后 enumsLoaded = true，避免重复拉取。
    enums: {
      platforms: [],
      templates: [],
      scriptTypes: [],
      emotions: [],
      speeds: [],
      ruleCategories: [],
      knowledgeCategories: [],
    },
    enumsLoaded: false,

    modelConfigs: [], // [ModelConfigOut]
    agents: [], // [AgentSummaryOut]
    currentAgentId: null,
    currentModelConfigId: null,
    // 当前打开的 Agent 详情（含 rules + knowledge），由 fetchAgentDetail 写入。
    currentAgentDetail: null,

    lastResult: null, // 最近一次 GenerateResponse

    history: _loadHistory(), // 本地 localStorage 缓存（≤50 条）
    historyOverflow: false, // localStorage 配额超限 trim 后给 UI 弹 toast 的 flag

    // 后端分页历史 —— 与本地 history 并存，UI 自行切换 tab 展示
    serverHistory: { items: [], total: 0, loadedAt: 0 },

    loading: {
      generate: false,
      models: false,
      agents: false,
      rules: false,
      knowledge: false,
      history: false,
    },
  }),

  getters: {
    currentAgent: (s) =>
      s.currentAgentId == null
        ? null
        : s.agents.find((a) => a.id === s.currentAgentId) || null,
    currentModelConfig: (s) =>
      s.currentModelConfigId == null
        ? null
        : s.modelConfigs.find((m) => m.id === s.currentModelConfigId) || null,
    isGenerating: (s) => !!s.loading.generate,
  },

  actions: {
    // ────────────────────────────────────────────────────────────────────
    // Enums
    // ────────────────────────────────────────────────────────────────────
    async fetchEnums(force = false) {
      if (this.enumsLoaded && !force) return this.enums;
      const data = await copyGenApi.getEnums();
      this.enums = {
        platforms: Array.isArray(data?.platforms) ? data.platforms : [],
        templates: Array.isArray(data?.templates) ? data.templates : [],
        scriptTypes: Array.isArray(data?.script_types) ? data.script_types : [],
        emotions: Array.isArray(data?.emotions) ? data.emotions : [],
        speeds: Array.isArray(data?.speeds) ? data.speeds : [],
        ruleCategories: Array.isArray(data?.rule_categories)
          ? data.rule_categories
          : [],
        knowledgeCategories: Array.isArray(data?.knowledge_categories)
          ? data.knowledge_categories
          : [],
      };
      this.enumsLoaded = true;
      return this.enums;
    },

    // ────────────────────────────────────────────────────────────────────
    // Model Configs
    // ────────────────────────────────────────────────────────────────────
    async fetchModelConfigs() {
      this.loading.models = true;
      try {
        const list = await copyGenApi.listModelConfigs();
        this.modelConfigs = Array.isArray(list) ? list : [];
        return this.modelConfigs;
      } finally {
        this.loading.models = false;
      }
    },

    async createModelConfig(payload) {
      this.loading.models = true;
      try {
        const created = await copyGenApi.createModelConfig(payload);
        if (created && created.id != null) {
          this.modelConfigs = [created, ...this.modelConfigs];
        }
        return created;
      } finally {
        this.loading.models = false;
      }
    },

    async updateModelConfig(id, patch) {
      this.loading.models = true;
      try {
        const updated = await copyGenApi.updateModelConfig(id, patch);
        if (updated && updated.id != null) {
          this.modelConfigs = this.modelConfigs.map((m) =>
            m.id === updated.id ? updated : m
          );
        }
        return updated;
      } finally {
        this.loading.models = false;
      }
    },

    async deleteModelConfig(id) {
      this.loading.models = true;
      try {
        const resp = await copyGenApi.deleteModelConfig(id);
        this.modelConfigs = this.modelConfigs.filter((m) => m.id !== id);
        if (this.currentModelConfigId === id) {
          this.currentModelConfigId = null;
        }
        return resp;
      } finally {
        this.loading.models = false;
      }
    },

    async testModelConfig(id) {
      // 不占用 models loading（这是连通性测试，不是 CRUD），调用方自管 loading flag。
      return await copyGenApi.testModelConfig(id);
    },

    // ────────────────────────────────────────────────────────────────────
    // Agents
    // ────────────────────────────────────────────────────────────────────
    async fetchAgents() {
      this.loading.agents = true;
      try {
        const list = await copyGenApi.listAgents();
        this.agents = Array.isArray(list) ? list : [];
        return this.agents;
      } finally {
        this.loading.agents = false;
      }
    },

    async fetchAgentDetail(id) {
      this.loading.agents = true;
      try {
        const detail = await copyGenApi.getAgentDetail(id);
        this.currentAgentDetail = detail || null;
        return detail;
      } finally {
        this.loading.agents = false;
      }
    },

    async createAgent(payload) {
      this.loading.agents = true;
      try {
        const created = await copyGenApi.createAgent(payload);
        if (created && created.id != null) {
          // 后端返回 AgentDetailOut；列表用 summary 字段，这里取交集即可。
          this.agents = [created, ...this.agents];
          this.currentAgentDetail = created;
        }
        return created;
      } finally {
        this.loading.agents = false;
      }
    },

    async updateAgent(id, patch) {
      this.loading.agents = true;
      try {
        const updated = await copyGenApi.updateAgent(id, patch);
        if (updated && updated.id != null) {
          this.agents = this.agents.map((a) =>
            a.id === updated.id ? { ...a, ...updated } : a
          );
          if (this.currentAgentDetail?.id === updated.id) {
            this.currentAgentDetail = updated;
          }
        }
        return updated;
      } finally {
        this.loading.agents = false;
      }
    },

    async deleteAgent(id) {
      this.loading.agents = true;
      try {
        const resp = await copyGenApi.deleteAgent(id);
        this.agents = this.agents.filter((a) => a.id !== id);
        if (this.currentAgentId === id) this.currentAgentId = null;
        if (this.currentAgentDetail?.id === id) this.currentAgentDetail = null;
        return resp;
      } finally {
        this.loading.agents = false;
      }
    },

    // ────────────────────────────────────────────────────────────────────
    // Rules
    // ────────────────────────────────────────────────────────────────────
    async createRule(agentId, payload) {
      this.loading.rules = true;
      try {
        const created = await copyGenApi.createRule(agentId, payload);
        if (this.currentAgentDetail?.id === agentId && created) {
          const rules = Array.isArray(this.currentAgentDetail.rules)
            ? this.currentAgentDetail.rules.slice()
            : [];
          rules.push(created);
          this.currentAgentDetail = { ...this.currentAgentDetail, rules };
        }
        return created;
      } finally {
        this.loading.rules = false;
      }
    },

    async updateRule(agentId, rid, patch) {
      this.loading.rules = true;
      try {
        const updated = await copyGenApi.updateRule(agentId, rid, patch);
        if (this.currentAgentDetail?.id === agentId && updated) {
          const rules = (this.currentAgentDetail.rules || []).map((r) =>
            r.id === updated.id ? updated : r
          );
          this.currentAgentDetail = { ...this.currentAgentDetail, rules };
        }
        return updated;
      } finally {
        this.loading.rules = false;
      }
    },

    async deleteRule(agentId, rid) {
      this.loading.rules = true;
      try {
        const resp = await copyGenApi.deleteRule(agentId, rid);
        if (this.currentAgentDetail?.id === agentId) {
          const rules = (this.currentAgentDetail.rules || []).filter(
            (r) => r.id !== rid
          );
          this.currentAgentDetail = { ...this.currentAgentDetail, rules };
        }
        return resp;
      } finally {
        this.loading.rules = false;
      }
    },

    // ────────────────────────────────────────────────────────────────────
    // Knowledge
    // ────────────────────────────────────────────────────────────────────
    async createKnowledge(agentId, payload) {
      this.loading.knowledge = true;
      try {
        const created = await copyGenApi.createKnowledge(agentId, payload);
        if (this.currentAgentDetail?.id === agentId && created) {
          const knowledge = Array.isArray(this.currentAgentDetail.knowledge)
            ? this.currentAgentDetail.knowledge.slice()
            : [];
          knowledge.push(created);
          this.currentAgentDetail = { ...this.currentAgentDetail, knowledge };
        }
        return created;
      } finally {
        this.loading.knowledge = false;
      }
    },

    async updateKnowledge(agentId, kid, patch) {
      this.loading.knowledge = true;
      try {
        const updated = await copyGenApi.updateKnowledge(agentId, kid, patch);
        if (this.currentAgentDetail?.id === agentId && updated) {
          const knowledge = (this.currentAgentDetail.knowledge || []).map((k) =>
            k.id === updated.id ? updated : k
          );
          this.currentAgentDetail = { ...this.currentAgentDetail, knowledge };
        }
        return updated;
      } finally {
        this.loading.knowledge = false;
      }
    },

    async deleteKnowledge(agentId, kid) {
      this.loading.knowledge = true;
      try {
        const resp = await copyGenApi.deleteKnowledge(agentId, kid);
        if (this.currentAgentDetail?.id === agentId) {
          const knowledge = (this.currentAgentDetail.knowledge || []).filter(
            (k) => k.id !== kid
          );
          this.currentAgentDetail = { ...this.currentAgentDetail, knowledge };
        }
        return resp;
      } finally {
        this.loading.knowledge = false;
      }
    },

    // ────────────────────────────────────────────────────────────────────
    // Generation
    // ────────────────────────────────────────────────────────────────────
    async generate(payload, options = {}) {
      this.loading.generate = true;
      try {
        const result = await copyGenApi.generate(payload, options);
        this.lastResult = result;
        this.addLocalHistory({
          ts: Date.now(),
          mode: "quick",
          agent_id: null,
          model_config_id:
            payload?.model_config_id ?? this.currentModelConfigId ?? null,
          payload,
          result,
        });
        return result;
      } finally {
        this.loading.generate = false;
      }
    },

    async generateWithAgent(agentId, payload, options = {}) {
      this.loading.generate = true;
      try {
        const result = await copyGenApi.generateWithAgent(
          agentId,
          payload,
          options
        );
        this.lastResult = result;
        this.addLocalHistory({
          ts: Date.now(),
          mode: "agent",
          agent_id: agentId,
          model_config_id:
            payload?.model_config_id ?? this.currentModelConfigId ?? null,
          payload,
          result,
        });
        return result;
      } finally {
        this.loading.generate = false;
      }
    },

    // ────────────────────────────────────────────────────────────────────
    // Server-side history
    // ────────────────────────────────────────────────────────────────────
    async fetchServerHistory({ limit = 20, offset = 0 } = {}) {
      this.loading.history = true;
      try {
        const data = await copyGenApi.listHistory({ limit, offset });
        this.serverHistory = {
          items: Array.isArray(data?.items) ? data.items : [],
          total: typeof data?.total === "number" ? data.total : 0,
          loadedAt: Date.now(),
        };
        return this.serverHistory;
      } finally {
        this.loading.history = false;
      }
    },

    async deleteServerHistory(id) {
      this.loading.history = true;
      try {
        const resp = await copyGenApi.deleteHistory(id);
        this.serverHistory = {
          ...this.serverHistory,
          items: this.serverHistory.items.filter((it) => it.id !== id),
          total: Math.max(0, (this.serverHistory.total || 0) - 1),
        };
        return resp;
      } finally {
        this.loading.history = false;
      }
    },

    // ────────────────────────────────────────────────────────────────────
    // Current-selection setters
    // ────────────────────────────────────────────────────────────────────
    setCurrentAgentId(id) {
      this.currentAgentId = id == null ? null : id;
    },
    setCurrentModelConfigId(id) {
      this.currentModelConfigId = id == null ? null : id;
    },

    // ────────────────────────────────────────────────────────────────────
    // Local history (localStorage)
    // ────────────────────────────────────────────────────────────────────
    addLocalHistory(item) {
      const next = [item, ...this.history];
      if (next.length > HISTORY_MAX) next.length = HISTORY_MAX;
      this.history = next;
      this._persistHistory();
    },

    clearLocalHistory() {
      this.history = [];
      this.historyOverflow = false;
      this._persistHistory();
    },

    deleteLocalHistoryAt(idx) {
      if (idx < 0 || idx >= this.history.length) return;
      const next = this.history.slice();
      next.splice(idx, 1);
      this.history = next;
      this._persistHistory();
    },

    // 让 UI 在弹完 toast 后调用以重置标志（同 tts.js 模式）
    acknowledgeHistoryOverflow() {
      this.historyOverflow = false;
    },

    // 内部：把当前 history 持久化到 localStorage；遇到配额超限会自动 trim 至一半，
    // 并同步 store 内的 history 数组，让 UI 显示一致。
    _persistHistory() {
      const r = _saveHistory(this.history);
      if (r && r.trimmedLength != null && r.trimmedLength !== this.history.length) {
        this.history = this.history.slice(0, r.trimmedLength);
      }
      if (r && r.overflow) {
        this.historyOverflow = true;
      }
    },

    setLocale(locale) {
      _setLocale(locale);
    },
  },
});

function _loadHistory() {
  try {
    const v = JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
    return Array.isArray(v) ? v : [];
  } catch {
    return [];
  }
}

// 返回结构（同 tts.js）：
//   { ok: true,  overflow: false, trimmedLength: null }  正常写入
//   { ok: true,  overflow: true,  trimmedLength: N }     配额超限 → trim 到 N 条后写入成功
//   { ok: false, overflow: true,  trimmedLength: null }  trim 后仍失败
//   { ok: false, overflow: false, trimmedLength: null }  非 quota 异常（JSON 错等）
function _saveHistory(history) {
  const serialized = (() => {
    try {
      return JSON.stringify(history);
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error("[CopyGen] history serialize failed:", e);
      return null;
    }
  })();
  if (serialized == null) {
    return { ok: false, overflow: false, trimmedLength: null };
  }
  try {
    localStorage.setItem(HISTORY_KEY, serialized);
    return { ok: true, overflow: false, trimmedLength: null };
  } catch (e) {
    const isQuota =
      e &&
      (e.name === "QuotaExceededError" ||
        e.code === 22 ||
        e.name === "NS_ERROR_DOM_QUOTA_REACHED" ||
        e.code === 1014);
    if (!isQuota) {
      // eslint-disable-next-line no-console
      console.error("[CopyGen] history save failed:", e);
      return { ok: false, overflow: false, trimmedLength: null };
    }
    // 配额超限：trim 到一半再试
    const newLen = Math.max(1, Math.floor(history.length / 2));
    const trimmed = history.slice(0, newLen);
    try {
      localStorage.setItem(HISTORY_KEY, JSON.stringify(trimmed));
      // eslint-disable-next-line no-console
      console.warn(
        "[CopyGen] history trimmed to",
        trimmed.length,
        "entries due to quota"
      );
      return { ok: true, overflow: true, trimmedLength: trimmed.length };
    } catch (e2) {
      // eslint-disable-next-line no-console
      console.warn("[CopyGen] history save still failed after trim:", e2);
      return { ok: false, overflow: true, trimmedLength: null };
    }
  }
}
