import axios from "axios";

/** 给直接浏览器访问的下载/预览 URL 追加 token 查询参数。
 *  <a href>, window.open, <video src>, <img src> 无法携带 Authorization header，
 *  后端 auth middleware 同步支持 ?token= 作为备用认证方式。
 */
export function withAuthToken(url) {
  const token = localStorage.getItem("vmis_token");
  if (!token) return url;
  const sep = url.includes("?") ? "&" : "?";
  return `${url}${sep}token=${encodeURIComponent(token)}`;
}

export const api = axios.create({
  baseURL: "/api",
  timeout: 30000,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("vmis_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  try {
    const user = JSON.parse(localStorage.getItem("vmis_user"));
    if (user?.username) {
      config.headers["X-Operator"] = user.username;
    }
  } catch {
    // ignore
  }
  return config;
});

api.interceptors.response.use(
  (resp) => resp,
  (err) => {
    if (err?.response?.status === 401) {
      localStorage.removeItem("vmis_token");
      localStorage.removeItem("vmis_user");
      if (!window.location.pathname.includes("/login")) {
        window.location.href = "/login";
      }
      return Promise.reject(err);
    }
    const detail = err?.response?.data?.detail;
    if (typeof detail === "string" && detail) {
      err.message = detail;
    } else if (detail?.message) {
      err.message = detail.message;
    }
    return Promise.reject(err);
  }
);
