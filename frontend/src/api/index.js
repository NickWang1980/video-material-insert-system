import axios from "axios";

export const api = axios.create({
  baseURL: "/api",
  timeout: 30000,
});

api.interceptors.response.use(
  (resp) => resp,
  (err) => {
    const detail = err?.response?.data?.detail;
    if (typeof detail === "string" && detail) {
      err.message = detail;
    } else if (detail?.message) {
      err.message = detail.message;
    }
    return Promise.reject(err);
  }
);
