import { api, withAuthToken } from "./index";

export async function listSourceVideos() {
  const { data } = await api.get("/source-videos");
  return data;
}

export async function createSourceVideo({ name, video, subtitle }) {
  const form = new FormData();
  if (name) form.append("name", name);
  form.append("video", video);
  if (subtitle) {
    form.append("subtitle", subtitle);
  }
  const { data } = await api.post("/source-videos", form);
  return data;
}

export async function renameSourceVideo(id, name) {
  const { data } = await api.put(`/source-videos/${id}`, { name });
  return data;
}

export async function deleteSourceVideo(id) {
  const { data } = await api.delete(`/source-videos/${id}`);
  return data;
}

export async function retrySourceVideoAsr(id) {
  const { data } = await api.post(`/source-videos/${id}/asr/retry`);
  return data;
}

export function downloadSourceVideoAudioUrl(id, format = "wav") {
  const safeFormat = format === "flac" ? "flac" : "wav";
  return withAuthToken(`/api/source-videos/${id}/audio?format=${safeFormat}`);
}

export function downloadSourceVideoSubtitleUrl(id, source = "uploaded") {
  const safeSource = source === "asr" ? "asr" : "uploaded";
  return withAuthToken(`/api/source-videos/${id}/subtitle?source=${safeSource}`);
}

export async function getParsedSubtitle(id, source = "uploaded") {
  const safeSource = source === "asr" ? "asr" : "uploaded";
  const { data } = await api.get(`/source-videos/${id}/subtitle/parsed`, {
    params: { source: safeSource },
  });
  return data;
}
