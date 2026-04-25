import { createRouter, createWebHistory } from "vue-router";

import Home from "../views/Home.vue";
import TaskList from "../views/TaskList.vue";
import TaskDetail from "../views/TaskDetail.vue";
import ConfigList from "../views/ConfigList.vue";
import ConfigEditor from "../views/ConfigEditor.vue";
import MaterialLibrary from "../views/MaterialLibrary.vue";
import SourceVideoLibrary from "../views/SourceVideoLibrary.vue";
import Settings from "../views/Settings.vue";
import RoughCutUnit from "../views/RoughCutUnit.vue";

const routes = [
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
  { path: "/settings", name: "settings", component: Settings },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
