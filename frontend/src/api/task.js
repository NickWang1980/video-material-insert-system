import { api, withAuthToken } from "./index";

export async function getStats() {
  const { data } = await api.get("/stats");
  return data;
}

export async function listTasks(params = {}) {
  const { data } = await api.get("/tasks", { params });
  return data;
}

export async function getTask(id) {
  const { data } = await api.get(`/tasks/${id}`);
  return data;
}

export async function createTask({
  task_name,
  source_entry_id,
  config_ids,
  subtitle_source = "uploaded",
  add_subtitle_to_video = false,
  collision_priority = null,
}) {
  const form = new FormData();
  form.append("task_name", task_name);
  form.append("source_entry_id", String(source_entry_id));
  form.append("subtitle_source", subtitle_source === "asr" ? "asr" : "uploaded");
  form.append("add_subtitle_to_video", String(!!add_subtitle_to_video));
  (config_ids || []).forEach((id) => form.append("config_ids", String(id)));
  if (collision_priority && typeof collision_priority === "object") {
    form.append("collision_priority_json", JSON.stringify(collision_priority));
  }
  const { data } = await api.post("/tasks", form);
  return data;
}

export async function checkKeywordCollision({
  source_entry_id,
  config_ids,
  subtitle_source = "uploaded",
}) {
  const { data } = await api.post("/tasks/keyword-collision-check", {
    source_entry_id,
    config_ids: config_ids || [],
    subtitle_source: subtitle_source === "asr" ? "asr" : "uploaded",
  });
  return data;
}

export async function retryTask(id) {
  const { data } = await api.post(`/tasks/${id}/retry`);
  return data;
}

export async function stopTask(id) {
  const { data } = await api.post(`/tasks/${id}/stop`);
  return data;
}

export async function deleteTask(id) {
  const { data } = await api.delete(`/tasks/${id}`);
  return data;
}

export function downloadOutputUrl(id) {
  return withAuthToken(`/api/tasks/${id}/output`);
}

export function downloadReportUrl(id) {
  return withAuthToken(`/api/tasks/${id}/report`);
}

export function downloadLogUrl(id) {
  return withAuthToken(`/api/tasks/${id}/log`);
}

export async function getLogText(id, tail_kb = 256) {
  const token = localStorage.getItem("vmis_token");
  const resp = await fetch(`/api/tasks/${id}/log/text?tail_kb=${tail_kb}`, {
    headers: { Accept: "text/plain", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  });
  if (!resp.ok) throw new Error("获取日志失败");
  return await resp.text();
}
