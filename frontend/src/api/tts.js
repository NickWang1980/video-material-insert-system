import { api, withAuthToken } from "./index";

export async function getTTSStatus() {
  const { data } = await api.get("/tts/status");
  return data;
}

export async function loadTTSBase() {
  const { data } = await api.post("/tts/load");
  return data;
}

export async function loadTTSCustom() {
  const { data } = await api.post("/tts/load-custom");
  return data;
}

export async function unloadTTS() {
  const { data } = await api.post("/tts/unload");
  return data;
}

export async function synthesizeTTS(payload, options = {}) {
  // 首次合成会触发 ~1.7 GB 模型懒加载/下载，后端阻塞 30–90s（甚至更久）。
  // 全局 axios timeout 是 30s，对常规 API 合理但对合成不够 —— 这里单独抬到 3 分钟。
  // 调用方可传 { signal } 用于 AbortController 中止（批量合成 stop 用）。
  const { data } = await api.post("/tts/synthesize", payload, {
    timeout: 180000,
    signal: options.signal,
  });
  return data;
}

export async function uploadTTSReference(file) {
  const form = new FormData();
  form.append("audio", file);
  const { data } = await api.post("/tts/upload-reference", form);
  return data;
}

export async function getTTSVoices() {
  const { data } = await api.get("/tts/voices");
  return data;
}

export async function getTTSLanguages() {
  const { data } = await api.get("/tts/languages");
  return data;
}

export async function getTTSEmotions() {
  const { data } = await api.get("/tts/emotions");
  return data;
}

export async function listTTSModels() {
  const { data } = await api.get("/tts/models");
  return data;
}

export async function deleteTTSModel(key) {
  const { data } = await api.delete(`/tts/models/${encodeURIComponent(key)}`);
  return data;
}

/**
 * 接收 "/api/tts/audio/foo.wav"、"tts/audio/foo.wav" 或单纯文件名 "foo.wav"，
 * 返回带 token 的可直接在浏览器中访问的下载/预览 URL。
 */
export function getTTSAudioUrl(filenameOrAudioUrl) {
  if (!filenameOrAudioUrl) return "";
  const value = String(filenameOrAudioUrl).trim();
  if (!value) return "";
  let url;
  if (value.startsWith("/api/")) {
    url = value;
  } else if (value.startsWith("api/")) {
    url = `/${value}`;
  } else if (value.startsWith("/tts/")) {
    url = `/api${value}`;
  } else if (value.startsWith("http://") || value.startsWith("https://")) {
    return withAuthToken(value);
  } else {
    // 仅文件名（可能含子路径），去除可能的前导斜杠
    const name = value.replace(/^\/+/, "");
    url = `/api/tts/audio/${name}`;
  }
  return withAuthToken(url);
}
