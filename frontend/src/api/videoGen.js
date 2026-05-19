import { api, withAuthToken } from "./index";

export async function getVideoGenHealth() {
  const { data } = await api.get("/video-gen/health");
  return data;
}

/** Spawn vendor/heygem/start_api.bat in a new detached cmd window (Windows only).
 *  Idempotent: if heygem already reachable, server returns already_running=true. */
export async function startHeygemSidecar() {
  const { data } = await api.post("/video-gen/heygem/start");
  return data;
}

/**
 * 创建视频生成任务。
 * @param {Object} payload  { task_name, audio_source_type, audio_source_ref, video_source_type, video_source_ref }
 * @param {File|null} audioFile  当 audio_source_type === 'upload' 时必填
 * @param {File|null} videoFile  当 video_source_type === 'upload' 时必填
 */
export async function createVideoGenTask(payload, audioFile = null, videoFile = null) {
  const form = new FormData();
  form.append("payload", JSON.stringify(payload));
  if (audioFile) form.append("audio_file", audioFile);
  if (videoFile) form.append("video_file", videoFile);
  // 数字人合成 + 大文件上传，超时抬高到 30 分钟（实际后台 polling，主请求只到 create 返回）
  const { data } = await api.post("/video-gen", form, { timeout: 1800000 });
  return data;
}

export async function listVideoGenTasks(limit = 20, offset = 0) {
  const { data } = await api.get("/video-gen", { params: { limit, offset } });
  return data;
}

export async function getVideoGenTask(id) {
  const { data } = await api.get(`/video-gen/${id}`);
  return data;
}

export async function cancelVideoGenTask(id) {
  const { data } = await api.post(`/video-gen/${id}/cancel`);
  return data;
}

export function getVideoGenDownloadUrl(id) {
  return withAuthToken(`/api/video-gen/${id}/download`);
}

export async function saveVideoGenToMaterial(id, body) {
  const { data } = await api.post(`/video-gen/${id}/save-to-material`, body);
  return data;
}
