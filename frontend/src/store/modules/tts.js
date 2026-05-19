import { defineStore } from "pinia";
import * as ttsApi from "../../api/tts";
import { setLocale as _setLocale } from "../../locale";

const HISTORY_KEY = "vmis_tts_history";
const HISTORY_MAX = 50;

// --- Polling reference counter (module scope, non-reactive) ---
// 多个组件可能同时调用 startPolling（例如 TTSModelStatus + TTSStudio）。
// 用引用计数确保 stopPolling 只在最后一个 caller 退出时真正 clearInterval，
// 避免：（1）一个组件 unmount 时 stop 掉另一个仍在用的轮询；
//       （2）TTSStudio 复用 / HMR 时残留 timer。
let _pollingRefs = 0;
let _pollingTimer = null;

export const useTTSStore = defineStore("tts", {
  state: () => ({
    status: {
      phase: "idle",
      percent: 0,
      detail: "",
      message: "",
      error: null,
      elapsed_sec: 0,
      ready: false,
      base_loaded: false,
      custom_loaded: false,
      loaded_models: [],
    },
    voices: [],
    languages: [],
    emotions: [],
    enumsLoaded: false,
    // 保留 pollingTimer 字段仅为向后兼容（外部如果还有读，会得到 boolean-like）。
    // 真正的 timer 句柄走模块顶层 _pollingTimer 以配合引用计数。
    pollingTimer: null,
    history: _loadHistory(),
    lastResult: null,
    // localStorage 配额超限时 trim 至一半的提示 flag，由 UI 层 watch 后弹 toast。
    historyOverflow: false,
  }),
  getters: {
    isLoading: (s) => s.status.phase === "loading",
    isReady: (s) =>
      s.status.phase === "ready" ||
      (Array.isArray(s.status.loaded_models) && s.status.loaded_models.length > 0),
  },
  actions: {
    async fetchStatus() {
      try {
        const data = await ttsApi.getTTSStatus();
        this.status = {
          phase: data?.phase ?? "idle",
          percent: typeof data?.percent === "number" ? data.percent : 0,
          detail: data?.detail ?? "",
          message: data?.message ?? "",
          error: data?.error ?? null,
          elapsed_sec:
            typeof data?.elapsed_sec === "number" ? data.elapsed_sec : 0,
          ready: !!data?.ready,
          base_loaded: !!data?.base_loaded,
          custom_loaded: !!data?.custom_loaded,
          loaded_models: Array.isArray(data?.loaded_models)
            ? data.loaded_models
            : [],
        };
        return this.status;
      } catch (err) {
        // 拉取失败不应破坏轮询；将错误信息写到 status 但保持 phase
        this.status = {
          ...this.status,
          error: err?.message || String(err),
        };
        throw err;
      }
    },

    startPolling(intervalMs = 2000) {
      // 引用计数 +1，已在轮询则不再创建 timer
      _pollingRefs += 1;
      if (_pollingTimer) {
        return;
      }
      // 立即触发一次，避免等待第一个 interval
      this.fetchStatus().catch(() => {});
      _pollingTimer = setInterval(() => {
        this.fetchStatus().catch(() => {});
      }, intervalMs);
      this.pollingTimer = true;
    },

    stopPolling() {
      // 引用计数 -1，只有降为 0 才真正清掉 interval
      _pollingRefs = Math.max(0, _pollingRefs - 1);
      if (_pollingRefs === 0 && _pollingTimer) {
        clearInterval(_pollingTimer);
        _pollingTimer = null;
        this.pollingTimer = null;
      }
    },

    // 紧急/调试用：强制清掉 polling 而无视引用计数（例如 HMR 场景）。
    forceStopPolling() {
      _pollingRefs = 0;
      if (_pollingTimer) {
        clearInterval(_pollingTimer);
        _pollingTimer = null;
      }
      this.pollingTimer = null;
    },

    async loadBase() {
      const resp = await ttsApi.loadTTSBase();
      this.startPolling();
      return resp;
    },

    async loadCustom() {
      const resp = await ttsApi.loadTTSCustom();
      this.startPolling();
      return resp;
    },

    async unloadAll() {
      const resp = await ttsApi.unloadTTS();
      await this.fetchStatus();
      return resp;
    },

    async fetchEnums() {
      if (this.enumsLoaded) return;
      const [voices, languages, emotions] = await Promise.all([
        ttsApi.getTTSVoices(),
        ttsApi.getTTSLanguages(),
        ttsApi.getTTSEmotions(),
      ]);
      this.voices = Array.isArray(voices) ? voices : [];
      this.languages = Array.isArray(languages) ? languages : [];
      this.emotions = Array.isArray(emotions) ? emotions : [];
      this.enumsLoaded = true;
    },

    async synthesize(payload) {
      const result = await ttsApi.synthesizeTTS(payload);
      this.lastResult = {
        ...payload,
        audio_url: result?.audio_url ?? "",
        duration_sec:
          typeof result?.duration_sec === "number" ? result.duration_sec : 0,
        status: result?.status,
        message: result?.message,
        ts: Date.now(),
      };
      this.addHistory({
        ts: Date.now(),
        text: payload?.text ?? "",
        language: payload?.language ?? "",
        voice: payload?.voice ?? "",
        ref_audio: payload?.ref_audio ?? "",
        emotion: payload?.emotion ?? "",
        speed: payload?.speed ?? 1.0,
        instruct: payload?.instruct ?? "",
        audio_url: result?.audio_url ?? "",
        duration_sec:
          typeof result?.duration_sec === "number" ? result.duration_sec : 0,
      });
      return result;
    },

    async uploadReference(file) {
      const resp = await ttsApi.uploadTTSReference(file);
      return resp?.ref_audio_path ?? "";
    },

    addHistory(item) {
      const next = [item, ...this.history];
      if (next.length > HISTORY_MAX) next.length = HISTORY_MAX;
      this.history = next;
      this._persistHistory();
    },

    clearHistory() {
      this.history = [];
      this.historyOverflow = false;
      this._persistHistory();
    },

    deleteHistoryAt(index) {
      if (index < 0 || index >= this.history.length) return;
      const next = this.history.slice();
      next.splice(index, 1);
      this.history = next;
      this._persistHistory();
    },

    // 让 UI 在弹完 toast 后调用以重置标志
    acknowledgeHistoryOverflow() {
      this.historyOverflow = false;
    },

    // 内部：把当前 history 持久化到 localStorage；遇到配额超限会自动 trim 至一半，
    // 并同步 store 内的 history 数组，让 UI 显示一致。
    _persistHistory() {
      const r = _saveHistory(this.history);
      if (r && r.trimmedLength != null && r.trimmedLength !== this.history.length) {
        // localStorage 已 trim 到 r.trimmedLength，把内存中的 history 也同步缩短
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

// 返回结构：
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
      console.error("[TTS] history serialize failed:", e);
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
      console.error("[TTS] history save failed:", e);
      return { ok: false, overflow: false, trimmedLength: null };
    }
    // 配额超限：trim 到一半再试
    const newLen = Math.max(1, Math.floor(history.length / 2));
    const trimmed = history.slice(0, newLen);
    try {
      localStorage.setItem(HISTORY_KEY, JSON.stringify(trimmed));
      // eslint-disable-next-line no-console
      console.warn(
        "[TTS] history trimmed to",
        trimmed.length,
        "entries due to quota"
      );
      return { ok: true, overflow: true, trimmedLength: trimmed.length };
    } catch (e2) {
      // eslint-disable-next-line no-console
      console.warn("[TTS] history save still failed after trim:", e2);
      return { ok: false, overflow: true, trimmedLength: null };
    }
  }
}
