import { defineStore } from "pinia";
import * as configApi from "../../api/config";

export const useConfigStore = defineStore("config", {
  state: () => ({
    templates: [],
    loading: false,
  }),
  actions: {
    async fetchTemplates() {
      this.loading = true;
      try {
        this.templates = await configApi.listTemplates();
      } finally {
        this.loading = false;
      }
    },
    async getTemplate(id) {
      return await configApi.getTemplate(id);
    },
    async createTemplate(payload) {
      return await configApi.createTemplate(payload);
    },
    async updateTemplate(id, payload) {
      return await configApi.updateTemplate(id, payload);
    },
    async deleteTemplate(id) {
      return await configApi.deleteTemplate(id);
    },
    async importCsv(file) {
      return await configApi.importCsv(file);
    },
    exportCsvUrl(id) {
      return configApi.exportCsvUrl(id);
    },
  },
});
