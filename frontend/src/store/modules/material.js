import { defineStore } from "pinia";
import * as materialApi from "../../api/material";

export const useMaterialStore = defineStore("material", {
  state: () => ({
    items: [],
    loading: false,
    fileType: "",
  }),
  actions: {
    async fetchList(fileType = "") {
      this.loading = true;
      this.fileType = fileType;
      try {
        this.items = await materialApi.listMaterials({ file_type: fileType || undefined });
      } finally {
        this.loading = false;
      }
    },
    async upload(files) {
      return await materialApi.uploadMaterials(files);
    },
    async rename(id, newName) {
      return await materialApi.renameMaterial(id, newName);
    },
    async remove(id) {
      return await materialApi.deleteMaterial(id);
    },
    previewUrl(id) {
      return materialApi.previewUrl(id);
    },
  },
});
