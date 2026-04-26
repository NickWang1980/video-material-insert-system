<template>
  <aside
    class="h-screen sticky top-0 border-r border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 transition-all duration-200"
    :class="collapsed ? 'w-[72px]' : 'w-[240px]'"
  >
    <div class="p-4 border-b border-gray-100 dark:border-gray-700">
      <div class="flex items-center" :class="collapsed ? 'justify-center' : 'justify-between gap-3'">
        <div class="flex items-center gap-3 min-w-0">
          <img src="/bzy_logo.png" alt="八爪鱼Logo" class="w-8 h-8 rounded-lg object-cover flex-none" />
          <div v-if="!collapsed" class="text-base font-bold leading-tight truncate text-gray-900 dark:text-gray-100">自动化剪辑工具</div>
        </div>
        <el-button text class="!px-2 dark:!text-gray-300" @click="$emit('toggle')">
          {{ collapsed ? "»" : "«" }}
        </el-button>
      </div>
      <div v-if="!collapsed" class="text-xs text-gray-500 dark:text-gray-400 mt-2">V2.0</div>
    </div>

    <nav class="p-3 space-y-1">
      <RouterLink
        v-for="item in items"
        :key="item.to"
        :to="item.to"
        class="block rounded-xl transition-colors"
        :class="[
          $route.path === item.to
            ? 'bg-black text-white dark:bg-white dark:text-gray-900'
            : 'text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700',
          collapsed ? 'px-0 py-2 text-center' : 'px-4 py-2'
        ]"
        :title="collapsed ? item.label : ''"
      >
        <span v-if="collapsed">{{ item.short }}</span>
        <span v-else>{{ item.label }}</span>
      </RouterLink>
    </nav>
  </aside>
</template>

<script setup>
import { computed } from "vue";
import { useAuthStore } from "../../store/modules/auth";

defineProps({
  collapsed: {
    type: Boolean,
    default: false,
  },
});

defineEmits(["toggle"]);

const authStore = useAuthStore();

const allItems = [
  { to: "/",              label: "控制台",   short: "控", moduleKey: "console" },
  { to: "/tasks",         label: "任务管理", short: "任", moduleKey: "tasks" },
  { to: "/configs",       label: "配置模板", short: "模", moduleKey: "configs" },
  { to: "/materials",     label: "素材库",   short: "材", moduleKey: "materials" },
  { to: "/source-videos", label: "源视频库", short: "源", moduleKey: "source_videos" },
  { to: "/rough-cut/unit",label: "混剪单元", short: "混", moduleKey: "rough_cut" },
  { to: "/audit",         label: "操作历史", short: "历", moduleKey: "audit" },
  { to: "/admin/users",   label: "权限控制", short: "权", moduleKey: "user_management", adminOnly: true },
  { to: "/settings",      label: "系统设置", short: "设", moduleKey: "settings" },
];

const items = computed(() =>
  allItems.filter((item) => {
    if (item.adminOnly && !authStore.isAdmin) return false;
    if (authStore.isAdmin) return true;
    return authStore.allowedModules.includes(item.moduleKey);
  })
);
</script>
