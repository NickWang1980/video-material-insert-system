import { api, withAuthToken } from "./index";

export async function listTemplates() {
  const { data } = await api.get("/config-templates");
  return data;
}

export async function getTemplate(id) {
  const { data } = await api.get(`/config-templates/${id}`);
  return data;
}

export async function createTemplate(payload) {
  const { data } = await api.post("/config-templates", payload);
  return data;
}

export async function updateTemplate(id, payload) {
  const { data } = await api.put(`/config-templates/${id}`, payload);
  return data;
}

export async function deleteTemplate(id) {
  const { data } = await api.delete(`/config-templates/${id}`);
  return data;
}

export async function importCsv(file) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post("/config-templates/import", form);
  return data;
}

export function exportCsvUrl(id) {
  return withAuthToken(`/api/config-templates/${id}/export`);
}
