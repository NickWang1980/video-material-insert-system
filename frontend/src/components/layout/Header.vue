<template>
  <header
    class="h-16 flex items-center justify-between px-8 border-b border-gray-100 bg-white dark:bg-gray-800 dark:border-gray-700 sticky top-0 z-10"
  >
    <div class="font-bold text-xl text-black dark:text-gray-100">{{ title }}</div>

    <div class="flex items-center gap-3">
      <!-- Current user -->
      <div v-if="authStore.isLoggedIn" class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-300">
        <span class="hidden sm:inline">{{ authStore.username }}</span>
        <el-tag
          :type="authStore.isAdmin ? '' : 'info'"
          size="small"
          effect="light"
        >
          {{ authStore.roleDisplayName || (authStore.isAdmin ? "管理员" : "普通用户") }}
        </el-tag>
        <el-button text size="small" class="!px-2 dark:!text-gray-300" @click="handleLogout">
          登出
        </el-button>
      </div>

      <!-- Theme picker: Light / Dark / Glass -->
      <div class="theme-picker">
        <button
          class="theme-btn"
          :class="{ 'theme-btn--active': theme === 'light' }"
          title="亮色模式"
          @click="$emit('set-theme', 'light')"
        >
          <!-- Sun -->
          <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="5"/>
            <line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
            <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
            <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
            <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
          </svg>
        </button>

        <button
          class="theme-btn"
          :class="{ 'theme-btn--active': theme === 'dark' }"
          title="暗色模式"
          @click="$emit('set-theme', 'dark')"
        >
          <!-- Moon -->
          <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
          </svg>
        </button>

        <button
          class="theme-btn"
          :class="{ 'theme-btn--active': theme === 'glass' }"
          title="液态玻璃"
          @click="$emit('set-theme', 'glass')"
        >
          <!-- Crystal / hexagon -->
          <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polygon points="12,3 21,8.5 21,15.5 12,21 3,15.5 3,8.5"/>
            <line x1="12" y1="3" x2="12" y2="21"/>
            <line x1="3" y1="8.5" x2="21" y2="8.5"/>
          </svg>
        </button>
      </div>
    </div>
  </header>
</template>

<script setup>
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "../../store/modules/auth";

defineProps({ theme: { type: String, default: "light" } });
defineEmits(["set-theme"]);

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();

const title = computed(() => {
  const map = {
    home: "控制台", tasks: "任务管理", taskDetail: "任务详情",
    configs: "配置模板", configNew: "新建模板", configEdit: "编辑模板",
    materials: "素材库", sourceVideos: "源视频库",
    roughCutUnit: "混剪单元", audit: "操作历史",
    userManagement: "权限控制", settings: "系统设置",
  };
  return map[route.name] || "短视频智能素材自动植入工具";
});

function handleLogout() {
  authStore.logout();
  router.push("/login");
}
</script>

<style>
/* ── Theme picker pill ── */
.theme-picker {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 3px;
  background: rgba(0, 0, 0, 0.06);
  border-radius: 999px;
}

.theme-btn {
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  border: none;
  background: transparent;
  color: #6b7280;
  cursor: pointer;
  transition: background 0.15s, color 0.15s, box-shadow 0.15s;
}

.theme-btn:hover {
  background: rgba(0, 0, 0, 0.06);
  color: #374151;
}

.theme-btn--active {
  background: #ffffff;
  color: #111827;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.15);
}

/* Dark mode */
html.dark .theme-picker {
  background: rgba(255, 255, 255, 0.08);
}
html.dark .theme-btn {
  color: rgba(255, 255, 255, 0.45);
}
html.dark .theme-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.75);
}
html.dark .theme-btn--active {
  background: rgba(255, 255, 255, 0.16);
  color: #fff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.35);
}

/* Glass mode */
html.glass .theme-picker {
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.12);
}
html.glass .theme-btn {
  color: rgba(255, 255, 255, 0.50);
}
html.glass .theme-btn:hover {
  background: rgba(255, 255, 255, 0.10);
  color: rgba(255, 255, 255, 0.82);
}
html.glass .theme-btn--active {
  background: rgba(255, 255, 255, 0.22);
  color: #fff;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.35), 0 2px 8px rgba(0, 0, 0, 0.25);
}
</style>
