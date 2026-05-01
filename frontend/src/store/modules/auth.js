import { defineStore } from "pinia";
import { loginApi } from "../../api/auth";
import { api } from "../../api/index";

const TOKEN_KEY = "vmis_token";
const USER_KEY = "vmis_user";

async function _fetchRoleDisplayName(roleName) {
  try {
    const { data } = await api.get("/roles");
    const found = data.find((r) => r.name === roleName);
    return found?.display_name || "";
  } catch {
    return "";
  }
}

export const useAuthStore = defineStore("auth", {
  state: () => ({
    token: localStorage.getItem(TOKEN_KEY) || null,
    user: (() => {
      try { return JSON.parse(localStorage.getItem(USER_KEY)); } catch { return null; }
    })(),
  }),
  getters: {
    isLoggedIn: (state) => !!state.token,
    isAdmin: (state) => state.user?.role === "admin",
    username: (state) => state.user?.username || "",
    role: (state) => state.user?.role || "",
    roleDisplayName: (state) => state.user?.role_display_name || "",
    allowedModules: (state) => state.user?.allowed_modules || [],
  },
  actions: {
    async login(username, password) {
      const data = await loginApi({ username, password });
      this.token = data.access_token;
      localStorage.setItem(TOKEN_KEY, this.token);
      const roleDisplayName = await _fetchRoleDisplayName(data.role);
      this.user = {
        username: data.username,
        role: data.role,
        role_display_name: roleDisplayName,
        allowed_modules: data.allowed_modules || [],
      };
      localStorage.setItem(USER_KEY, JSON.stringify(this.user));
    },
    logout() {
      this.token = null;
      this.user = null;
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
    },
  },
});
