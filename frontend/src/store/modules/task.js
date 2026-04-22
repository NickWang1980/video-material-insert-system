import { defineStore } from "pinia";
import * as taskApi from "../../api/task";

export const useTaskStore = defineStore("task", {
  state: () => ({
    items: [],
    total: 0,
    stats: null,
    loading: false,
  }),
  actions: {
    async fetchStats() {
      this.stats = await taskApi.getStats();
    },
    async fetchList(params = {}) {
      this.loading = true;
      try {
        const data = await taskApi.listTasks(params);
        this.items = data.items;
        this.total = data.total;
      } finally {
        this.loading = false;
      }
    },
    async fetchOne(id) {
      return await taskApi.getTask(id);
    },
    async create(payload) {
      return await taskApi.createTask(payload);
    },
    async checkKeywordCollision(payload) {
      return await taskApi.checkKeywordCollision(payload);
    },
    async retry(id) {
      return await taskApi.retryTask(id);
    },
    async stop(id) {
      return await taskApi.stopTask(id);
    },
    async remove(id) {
      return await taskApi.deleteTask(id);
    },
  },
});
