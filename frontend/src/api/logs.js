import { api, withAuthToken } from "./index";

export async function getLogCategories() {
  const { data } = await api.get("/logs/categories");
  return data;
}

export async function getLogItems(category) {
  const { data } = await api.get(`/logs/${encodeURIComponent(category)}/items`);
  return data;
}

export async function tailLog(category, itemId, lines = 1000) {
  const { data } = await api.get(
    `/logs/${encodeURIComponent(category)}/${encodeURIComponent(itemId)}/tail`,
    { params: { lines } }
  );
  return data;
}

export function logDownloadUrl(category, itemId) {
  return withAuthToken(
    `/api/logs/${encodeURIComponent(category)}/${encodeURIComponent(itemId)}/download`
  );
}
