import { defineStore } from "pinia";
import * as videoGenApi from "../../api/videoGen";

const VRAM_STRATEGY_KEY = "vmis_video_gen_vram_strategy";

// 共享 polling timer（多个组件同时启）。引用计数避免一个 unmount 杀掉另一个。
let _statusPollingRefs = 0;
let _statusPollingTimer = null;
let _taskPollingTimer = null;

export const useVideoGenStore = defineStore("videoGen", {
  state: () => ({
    health: {
      enabled: true,
      reachable: false,
      base_url: "",
      detail: "",
      heygem_ready: null,
      heygem_gpu: null,
      heygem_version: null,
    },
    tasks: [],
    tasksTotal: 0,
    currentTask: null,            // active task being viewed/polled
    creating: false,
    healthLoading: false,
    // Phase-1 仅前端持久化；Phase-2 后端会读这个值决定调度行为。
    vramStrategy: _loadVramStrategy(),
  }),
  getters: {
    isHealthy: (s) => s.health.enabled && s.health.reachable && s.health.heygem_ready === true,
  },
  actions: {
    async fetchHealth() {
      this.healthLoading = true;
      try {
        this.health = await videoGenApi.getVideoGenHealth();
      } catch (e) {
        this.health = {
          enabled: true,
          reachable: false,
          base_url: this.health.base_url || "",
          detail: e?.message || String(e),
          heygem_ready: false,
        };
      } finally {
        this.healthLoading = false;
      }
      return this.health;
    },

    startHealthPolling(intervalMs = 5000) {
      _statusPollingRefs += 1;
      if (_statusPollingTimer) return;
      this.fetchHealth().catch(() => {});
      _statusPollingTimer = setInterval(() => {
        this.fetchHealth().catch(() => {});
      }, intervalMs);
    },

    stopHealthPolling() {
      _statusPollingRefs = Math.max(0, _statusPollingRefs - 1);
      if (_statusPollingRefs === 0 && _statusPollingTimer) {
        clearInterval(_statusPollingTimer);
        _statusPollingTimer = null;
      }
    },

    async fetchTasks(limit = 20, offset = 0) {
      const data = await videoGenApi.listVideoGenTasks(limit, offset);
      this.tasks = data.items || [];
      this.tasksTotal = data.total || 0;
      return data;
    },

    async createTask(payload, audioFile, videoFile) {
      this.creating = true;
      try {
        const task = await videoGenApi.createVideoGenTask(payload, audioFile, videoFile);
        this.currentTask = task;
        this.startTaskPolling(task.id);
        return task;
      } finally {
        this.creating = false;
      }
    },

    async refreshCurrentTask() {
      if (!this.currentTask?.id) return null;
      try {
        const t = await videoGenApi.getVideoGenTask(this.currentTask.id);
        this.currentTask = t;
        return t;
      } catch {
        return this.currentTask;
      }
    },

    startTaskPolling(taskId, intervalMs = 2000) {
      this.stopTaskPolling();
      this.currentTask = this.currentTask || { id: taskId };
      const tick = async () => {
        try {
          const t = await videoGenApi.getVideoGenTask(taskId);
          this.currentTask = t;
          if (["succeeded", "failed", "cancelled", "interrupted"].includes(t.status)) {
            this.stopTaskPolling();
          }
        } catch {
          // keep polling; transient errors are OK
        }
      };
      tick();
      _taskPollingTimer = setInterval(tick, intervalMs);
    },

    stopTaskPolling() {
      if (_taskPollingTimer) {
        clearInterval(_taskPollingTimer);
        _taskPollingTimer = null;
      }
    },

    async cancelCurrent() {
      if (!this.currentTask?.id) return;
      await videoGenApi.cancelVideoGenTask(this.currentTask.id);
      await this.refreshCurrentTask();
      this.stopTaskPolling();
    },

    /** Ask backend to spawn vendor/heygem/start_api.bat. Then ramp up health
     *  polling for ~120s to detect "ready". Returns the server response so the
     *  caller can show 'already_running' vs 'started' vs error. */
    async startSidecarAndWait() {
      const resp = await videoGenApi.startHeygemSidecar();
      // boost polling cadence to 2s for up to 120s, then back to normal
      const original = _statusPollingTimer;
      if (original) {
        clearInterval(_statusPollingTimer);
        _statusPollingTimer = null;
      }
      const fast = setInterval(() => {
        this.fetchHealth().catch(() => {});
      }, 2000);
      // baseline fetch immediately
      this.fetchHealth().catch(() => {});
      setTimeout(() => {
        clearInterval(fast);
        // restore normal polling if any subscribers remain
        if (_statusPollingRefs > 0 && !_statusPollingTimer) {
          _statusPollingTimer = setInterval(() => {
            this.fetchHealth().catch(() => {});
          }, 5000);
        }
      }, 120000);
      return resp;
    },

    setVramStrategy(value) {
      if (!["manual", "tts_unload", "cuda_isolate"].includes(value)) return;
      this.vramStrategy = value;
      try {
        localStorage.setItem(VRAM_STRATEGY_KEY, value);
      } catch {
        // ignore
      }
    },
  },
});

function _loadVramStrategy() {
  try {
    const v = localStorage.getItem(VRAM_STRATEGY_KEY);
    if (v && ["manual", "tts_unload", "cuda_isolate"].includes(v)) return v;
  } catch {
    // ignore
  }
  return "manual";
}
