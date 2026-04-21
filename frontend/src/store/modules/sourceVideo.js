import { defineStore } from "pinia";
import * as sourceVideoApi from "../../api/sourceVideo";

export const useSourceVideoStore = defineStore("sourceVideo", {
  state: () => ({
    items: [],
    loading: false,
    subtitlePreviewLoading: false,
  }),
  actions: {
    async fetchList() {
      this.loading = true;
      try {
        this.items = await sourceVideoApi.listSourceVideos();
      } finally {
        this.loading = false;
      }
    },
    async create(payload) {
      return await sourceVideoApi.createSourceVideo(payload);
    },
    async rename(id, name) {
      return await sourceVideoApi.renameSourceVideo(id, name);
    },
    async remove(id) {
      return await sourceVideoApi.deleteSourceVideo(id);
    },
    async retryAsr(id) {
      return await sourceVideoApi.retrySourceVideoAsr(id);
    },
    audioDownloadUrl(id, format = "wav") {
      return sourceVideoApi.downloadSourceVideoAudioUrl(id, format);
    },
    subtitleDownloadUrl(id, source = "uploaded") {
      return sourceVideoApi.downloadSourceVideoSubtitleUrl(id, source);
    },
    async getParsedSubtitle(id, source = "uploaded") {
      this.subtitlePreviewLoading = true;
      try {
        return await sourceVideoApi.getParsedSubtitle(id, source);
      } finally {
        this.subtitlePreviewLoading = false;
      }
    },
  },
});
