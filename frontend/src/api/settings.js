import { api } from "./index";

export async function getSettings() {
  const { data } = await api.get("/settings");
  return data;
}

export async function updateSettings(payload) {
  const { data } = await api.put("/settings", payload);
  return data;
}

export async function checkAsrModelInstalled(model) {
  const { data } = await api.post("/settings/asr-model/check", { model });
  return data;
}

export async function installAsrModel(model) {
  const { data } = await api.post("/settings/asr-model/install", { model });
  return data;
}

export async function getAsrInstallProgress(taskId) {
  const { data } = await api.get(`/settings/asr-model/install-progress/${taskId}`);
  return data;
}

export async function cancelAsrInstall(taskId) {
  const { data } = await api.post(`/settings/asr-model/install/${taskId}/cancel`);
  return data;
}

export async function listAsrModels() {
  const { data } = await api.get(`/settings/asr-models`);
  return data;
}

export async function deleteAsrModel(model, includeHfCache = false) {
  const { data } = await api.delete(`/settings/asr-models`, {
    data: { model, include_hf_cache: includeHfCache },
  });
  return data;
}

export async function getFfmpegInfo() {
  const { data } = await api.get(`/settings/ffmpeg-info`);
  return data;
}

export async function getCacheInfo() {
  const { data } = await api.get(`/settings/cache-info`);
  return data;
}

export async function clearCache(categories) {
  const { data } = await api.post(`/settings/cache-clear`, { categories });
  return data;
}

export async function getAsrQueue() {
  const { data } = await api.get(`/settings/asr-queue`);
  return data;
}

export async function clearAsrQueue() {
  const { data } = await api.post(`/settings/asr-queue/clear`);
  return data;
}

export async function getFfmpegQueue() {
  const { data } = await api.get(`/settings/ffmpeg-queue`);
  return data;
}

export async function clearFfmpegQueue() {
  const { data } = await api.post(`/settings/ffmpeg-queue/clear`);
  return data;
}
