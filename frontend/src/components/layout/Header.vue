<template>
  <header class="h-16 flex items-center px-8 border-b border-gray-100 bg-white sticky top-0 z-10">
    <div class="font-bold text-xl">{{ title }}</div>
  </header>
</template>

<script setup>
import { computed } from "vue";
import { useRoute } from "vue-router";

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
