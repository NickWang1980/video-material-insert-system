<template>
  <header
    class="h-16 flex items-center justify-between px-8 border-b border-gray-100 bg-white dark:bg-gray-800 dark:border-gray-700 sticky top-0 z-10"
  >
    <div class="font-bold text-xl text-black dark:text-gray-100">{{ title }}</div>

    <button
      class="w-8 h-8 flex items-center justify-center rounded-full border border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
      :title="isDark ? '切换为亮色模式' : '切换为暗色模式'"
      @click="$emit('toggle-dark')"
    >
      <!-- Moon: shown in light mode to indicate "switch to dark" -->
      <svg
        v-if="!isDark"
        xmlns="http://www.w3.org/2000/svg"
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
      </svg>
      <!-- Sun: shown in dark mode to indicate "switch to light" -->
      <svg
        v-else
        xmlns="http://www.w3.org/2000/svg"
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <circle cx="12" cy="12" r="5" />
        <line x1="12" y1="1" x2="12" y2="3" />
        <line x1="12" y1="21" x2="12" y2="23" />
        <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
        <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
        <line x1="1" y1="12" x2="3" y2="12" />
        <line x1="21" y1="12" x2="23" y2="12" />
        <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
        <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
      </svg>
    </button>
  </header>
</template>

<script setup>
import { computed } from "vue";
import { useRoute } from "vue-router";

defineProps({
  isDark: {
    type: Boolean,
    default: false,
  },
});

defineEmits(["toggle-dark"]);

const route = useRoute();
const title = computed(() => {
  const map = {
    home: "控制台",
    tasks: "任务管理",
    taskDetail: "任务详情",
    configs: "配置模板",
    configNew: "新建模板",
    configEdit: "编辑模板",
    materials: "素材库",
    sourceVideos: "源视频库",
    roughCutUnit: "混剪单元",
    settings: "系统设置",
  };
  return map[route.name] || "短视频智能素材自动植入工具";
});
</script>
