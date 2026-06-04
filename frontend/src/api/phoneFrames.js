import { api, withAuthToken } from "./index";

export async function listPhoneFrames() {
  const { data } = await api.get("/phone-frames");
  return data;
}

export async function uploadPhoneFrame(file) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post("/phone-frames", form);
  return data;
}

export async function deletePhoneFrame(name) {
  const { data } = await api.delete(`/phone-frames/${encodeURIComponent(name)}`);
  return data;
}

export function phoneFrameFileUrl(name) {
  return withAuthToken(`/api/phone-frames/${encodeURIComponent(name)}/file`);
}
