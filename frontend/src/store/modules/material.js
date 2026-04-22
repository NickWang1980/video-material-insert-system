import { defineStore } from "pinia";
import * as materialApi from "../../api/material";

export const useMaterialStore = defineStore("material", {
  state: () => ({
    items: [],
    tree: {
      unfiled_label: "未归档",
      product_label: "产品分类素材",
      products: [],
    },
    loading: false,
  }),
  actions: {
    async fetchList(filters = {}) {
      this.loading = true;
      const params = {
        file_type: filters.file_type || undefined,
        library_kind: filters.library_kind || undefined,
        product_id: filters.product_id || undefined,
        script_folder_id: filters.script_folder_id || undefined,
      };
      try {
        this.items = await materialApi.listMaterials(params);
      } finally {
        this.loading = false;
      }
    },
    async fetchTree() {
      this.tree = await materialApi.getMaterialTree();
      return this.tree;
    },
    async createProduct(name) {
      return await materialApi.createMaterialProduct(name);
    },
    async renameProduct(id, name) {
      return await materialApi.renameMaterialProduct(id, name);
    },
    async deleteProduct(id) {
      return await materialApi.deleteMaterialProduct(id);
    },
    async createScriptFolder(productId, name) {
      return await materialApi.createMaterialScriptFolder(productId, name);
    },
    async renameScriptFolder(id, name) {
      return await materialApi.renameMaterialScriptFolder(id, name);
    },
    async deleteScriptFolder(id) {
      return await materialApi.deleteMaterialScriptFolder(id);
    },
    async upload(files, meta = {}) {
      return await materialApi.uploadMaterials(files, meta);
    },
    async fileMaterial(materialId, payload) {
      return await materialApi.fileMaterial(materialId, payload);
    },
    async unfileMaterialFromScript(materialId, scriptFolderId) {
      return await materialApi.unfileMaterialFromScript(materialId, scriptFolderId);
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
