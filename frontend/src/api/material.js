import { api, withAuthToken } from "./index";

export async function listMaterials(params = {}) {
  const { data } = await api.get("/materials", { params });
  return data;
}

export async function getMaterialTree() {
  const { data } = await api.get("/materials/tree");
  return data;
}

export async function createMaterialProduct(name) {
  const { data } = await api.post("/materials/products", { name });
  return data;
}

export async function renameMaterialProduct(id, name) {
  const { data } = await api.put(`/materials/products/${id}`, { name });
  return data;
}

export async function deleteMaterialProduct(id) {
  const { data } = await api.delete(`/materials/products/${id}`);
  return data;
}

export async function createMaterialScriptFolder(productId, name) {
  const { data } = await api.post(`/materials/products/${productId}/scripts`, { name });
  return data;
}

export async function renameMaterialScriptFolder(id, name) {
  const { data } = await api.put(`/materials/scripts/${id}`, { name });
  return data;
}

export async function deleteMaterialScriptFolder(id) {
  const { data } = await api.delete(`/materials/scripts/${id}`);
  return data;
}

export async function uploadMaterials(files, meta = {}) {
  const form = new FormData();
  for (const f of files) form.append("files", f);
  if (meta.library_kind) form.append("library_kind", meta.library_kind);
  if (meta.script_folder_id) form.append("script_folder_id", String(meta.script_folder_id));
  const { data } = await api.post("/materials", form);
  return data;
}

export async function fileMaterial(materialId, payload) {
  const { data } = await api.post(`/materials/${materialId}/file`, payload);
  return data;
}

export async function unfileMaterialFromScript(materialId, scriptFolderId) {
  const { data } = await api.delete(`/materials/${materialId}/folders/${scriptFolderId}`);
  return data;
}

export async function renameMaterial(id, newFileName) {
  const { data } = await api.put(`/materials/${id}`, { new_file_name: newFileName });
  return data;
}

export async function deleteMaterial(id) {
  const { data } = await api.delete(`/materials/${id}`);
  return data;
}

export function previewUrl(id) {
  return withAuthToken(`/api/materials/${id}/preview`);
}
