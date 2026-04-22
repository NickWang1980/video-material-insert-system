<template>
  <aside
    class="h-screen sticky top-0 border-r border-gray-200 bg-white transition-all duration-200"
    :class="collapsed ? 'w-[72px]' : 'w-[240px]'"
  >
    <div class="p-4 border-b border-gray-100">
      <div class="flex items-center" :class="collapsed ? 'justify-center' : 'justify-between gap-3'">
        <div class="flex items-center gap-3 min-w-0">
          <img src="/bzy_logo.png" alt="八爪鱼Logo" class="w-8 h-8 rounded-lg object-cover flex-none" />
          <div v-if="!collapsed" class="text-base font-bold leading-tight truncate">八爪鱼智能自动化剪辑工具</div>
        </div>
        <el-button text class="!px-2" @click="$emit('toggle')">
          {{ collapsed ? "»" : "«" }}
        </el-button>
      </div>
      <div v-if="!collapsed" class="text-xs text-gray-500 mt-2">V1.0</div>
    </div>

    <nav class="p-3 space-y-1">
      <RouterLink
        v-for="item in items"
        :key="item.to"
        :to="item.to"
        class="block rounded-xl hover:bg-gray-50"
        :class="[
          $route.path === item.to ? 'bg-black text-white' : 'text-black',
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
defineProps({
  collapsed: {
    type: Boolean,
    default: false,
  },
});

defineEmits(["toggle"]);

const items = [
  { to: "/", label: "控制台", short: "控" },
  { to: "/tasks", label: "任务管理", short: "任" },
  { to: "/configs", label: "配置模板", short: "模" },
  { to: "/materials", label: "素材库", short: "材" },
  { to: "/source-videos", label: "源视频库", short: "源" },
  { to: "/settings", label: "系统设置", short: "设" },
];
</script>
