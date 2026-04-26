import { api } from "./index";

export async function loginApi(payload) {
  const { data } = await api.post("/auth/login", payload);
  return data;
}

export async function meApi() {
  const { data } = await api.get("/auth/me");
  return data;
}
