import { api, withAuthToken } from "./index";

export async function listRoughCutProjects(page = 1, pageSize = 9) {
  const { data } = await api.get("/rough-cut/projects", { params: { page, page_size: pageSize } });
  return { items: data?.items || [], total: data?.total || 0 };
}

export async function createRoughCutProject(payload) {
  const { data } = await api.post("/rough-cut/projects", payload);
  return data;
}

export async function updateRoughCutProject(projectId, payload) {
  const { data } = await api.patch(`/rough-cut/projects/${projectId}`, payload);
  return data;
}

export async function getRoughCutProject(projectId) {
  const { data } = await api.get(`/rough-cut/projects/${projectId}`);
  return data;
}

export async function deleteRoughCutProject(projectId) {
  const { data } = await api.delete(`/rough-cut/projects/${projectId}`);
  return data;
}

export async function uploadRoughCutAssets(projectId, roleId, files) {
  const form = new FormData();
  form.append("role_id", roleId);
  (files || []).forEach((file) => form.append("files", file));
  const { data } = await api.post(`/rough-cut/projects/${projectId}/assets`, form);
  return data;
}

export async function listRoughCutAssets(projectId) {
  const { data } = await api.get(`/rough-cut/projects/${projectId}/assets`);
  return data || [];
}

export async function getRoughCutProjectCompare(projectId) {
  const { data } = await api.get(`/rough-cut/projects/${projectId}/compare`);
  return data;
}

export async function deleteRoughCutAsset(projectId, assetId) {
  const { data } = await api.delete(`/rough-cut/projects/${projectId}/assets/${assetId}`);
  return data;
}

export async function setRoughCutAssetManualGate(projectId, assetId, manualPassed) {
  const { data } = await api.patch(
    `/rough-cut/projects/${projectId}/assets/${assetId}/manual-gate`,
    { manualPassed: !!manualPassed }
  );
  return data;
}

export async function splitRoughCutScript(projectId, script) {
  const { data } = await api.post(`/rough-cut/projects/${projectId}/split-script`, {
    script: script ?? null,
  });
  return data;
}

export async function assignRoughCutRoles(projectId, payload) {
  const { data } = await api.post(`/rough-cut/projects/${projectId}/assign-roles`, payload);
  return data;
}

export async function updateRoughCutSettings(projectId, settings) {
  const { data } = await api.put(`/rough-cut/projects/${projectId}/settings`, { settings });
  return data;
}

export async function buildRoughCutTimeline(projectId, recalculateDurations = true) {
  const { data } = await api.post(`/rough-cut/projects/${projectId}/build-timeline`, {
    recalculateDurations,
  });
  return data;
}

export async function updateRoughCutSentence(projectId, sentenceId, payload) {
  const { data } = await api.patch(
    `/rough-cut/projects/${projectId}/sentences/${sentenceId}`,
    payload
  );
  return data;
}

export async function regenerateRoughCutSentence(projectId, sentenceId) {
  const { data } = await api.post(
    `/rough-cut/projects/${projectId}/regenerate-sentence/${sentenceId}`
  );
  return data;
}

export async function exportRoughCutProject(projectId, mode = "preview") {
  const { data } = await api.post(`/rough-cut/projects/${projectId}/export`, { mode });
  return data;
}

export async function stopRoughCutProject(projectId) {
  const { data } = await api.post(`/rough-cut/projects/${projectId}/stop`);
  return data;
}

export async function getRoughCutStatus(projectId) {
  const { data } = await api.get(`/rough-cut/projects/${projectId}/status`);
  return data;
}

export async function getRoughCutFfmpegStatus() {
  const { data } = await api.get(`/rough-cut/ffmpeg/status`);
  return data;
}

export async function getRoughCutAsrStatus() {
  const { data } = await api.get(`/rough-cut/asr/status`);
  return data;
}

export async function clearRoughCutFfmpegBlocked() {
  const { data } = await api.post(`/rough-cut/ffmpeg/clear`);
  return data;
}

export function getRoughCutMediaUrl(projectId, type = "preview") {
  const mediaType = type === "output" ? "output" : "preview";
  return withAuthToken(`/api/rough-cut/projects/${projectId}/media?type=${mediaType}`);
}

export function getRoughCutAssetMediaUrl(projectId, assetId) {
  return withAuthToken(`/api/rough-cut/projects/${projectId}/assets/${assetId}/media`);
}

export async function previewRoughCutSentence(projectId, sentenceId) {
  await api.post(`/rough-cut/projects/${projectId}/sentence-preview/${sentenceId}`);
}

export function getSentencePreviewUrl(projectId, sentenceId) {
  return withAuthToken(`/api/rough-cut/projects/${projectId}/sentence-preview/${sentenceId}/media`);
}

export async function exportRoughCutStoryboard(projectId) {
  const token = _mediaToken();
  const url = `/api/rough-cut/projects/${projectId}/storyboard-export${token ? `?token=${encodeURIComponent(token)}` : ""}`;
  const resp = await fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!resp.ok) throw new Error((await resp.text()) || "导出失败");
  const disposition = resp.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename\*?=(?:UTF-8'')?([^;]+)/i);
  const filename = match
    ? decodeURIComponent(match[1].replace(/"/g, ""))
    : `分镜头时序导出文件_${new Date().toISOString().slice(0, 10).replace(/-/g, "")}.json`;
  const blob = await resp.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(a.href);
}

export async function importRoughCutStoryboard(projectId, file) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post(`/rough-cut/projects/${projectId}/storyboard-import`, form);
  return data;
}
