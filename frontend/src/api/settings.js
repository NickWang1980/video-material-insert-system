import { api } from "./index";

export async function getSettings() {
  const { data } = await api.get("/settings");
  return data;
}

export async function updateSettings(payload) {
  try {
    const { data } = await api.put("/settings", payload);
    return data;
  } catch (error) {
    if (payload && Object.prototype.hasOwnProperty.call(payload, "asr_model")) {
      const fallbackPayload = { ...payload };
      delete fallbackPayload.asr_model;
      const { data } = await api.put("/settings", fallbackPayload);
      return data;
    }
    throw error;
  }
}
