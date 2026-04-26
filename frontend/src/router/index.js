import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "../store/modules/auth";

import Home from "../views/Home.vue";
import TaskList from "../views/TaskList.vue";
import TaskDetail from "../views/TaskDetail.vue";
import ConfigList from "../views/ConfigList.vue";
import ConfigEditor from "../views/ConfigEditor.vue";
import MaterialLibrary from "../views/MaterialLibrary.vue";
import SourceVideoLibrary from "../views/SourceVideoLibrary.vue";
import Settings from "../views/Settings.vue";
import RoughCutUnit from "../views/RoughCutUnit.vue";
import AuditLog from "../views/AuditLog.vue";
import UserManagement from "../views/UserManagement.vue";
import Login from "../views/Login.vue";

const routes = [
  { path: "/login", name: "login", component: Login, meta: { public: true } },
  { path: "/", name: "home", component: Home },
  { path: "/tasks", name: "tasks", component: TaskList },
  { path: "/tasks/:id", name: "taskDetail", component: TaskDetail, props: true },
  { path: "/configs", name: "configs", component: ConfigList },
  { path: "/configs/new", name: "configNew", component: ConfigEditor },
  { path: "/configs/:id", name: "configEdit", component: ConfigEditor, props: true },
  { path: "/materials", name: "materials", component: MaterialLibrary },
  { path: "/source-videos", name: "sourceVideos", component: SourceVideoLibrary },
  { path: "/rough-cut/multi-role", redirect: "/rough-cut/unit" },
  { path: "/rough-cut/unit", name: "roughCutUnit", component: RoughCutUnit },
  { path: "/audit", name: "audit", component: AuditLog },
  { path: "/admin/users", name: "userManagement", component: UserManagement, meta: { adminOnly: true } },
  { path: "/settings", name: "settings", component: Settings },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach((to, _from, next) => {
  const auth = useAuthStore();
  if (to.meta?.public) {
    // Redirect logged-in users away from login page
    if (auth.isLoggedIn) return next("/");
    return next();
  }
  if (!auth.isLoggedIn) {
    return next({ name: "login", query: { redirect: to.fullPath } });
  }
  if (to.meta?.adminOnly && !auth.isAdmin) {
    return next("/");
  }
  next();
});

export default router;
