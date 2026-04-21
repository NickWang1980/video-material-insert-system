import { api } from "./index";

export async function listMaterials(params = {}) {
  const { data } = await api.get("/materials", { params });
  return data;
}

export async function uploadMaterials(files) {
  const form = new FormData();
  for (const f of files) form.append("files", f);
  const { data } = await api.post("/materials", form);
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
  return `/api/materials/${id}/preview`;
}
