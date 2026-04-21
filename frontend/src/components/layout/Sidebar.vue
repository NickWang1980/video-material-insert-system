<template>
  <aside class="w-[240px] h-screen sticky top-0 border-r border-gray-200 bg-white">
    <div class="p-6 border-b border-gray-100">
      <div class="flex items-center gap-3">
        <img src="/bzy_logo.png" alt="八爪鱼Logo" class="w-8 h-8 rounded-lg object-cover" />
        <div class="text-lg font-bold leading-tight">八爪鱼智能自动化剪辑工具</div>
      </div>
      <div class="text-xs text-gray-500 mt-2">V1.0</div>
    </div>
    <nav class="p-4 space-y-1">
      <RouterLink
        v-for="item in items"
        :key="item.to"
        :to="item.to"
        class="block px-4 py-2 rounded-xl hover:bg-gray-50"
        :class="$route.path === item.to ? 'bg-black text-white' : 'text-black'"
      >
        {{ item.label }}
      </RouterLink>
    </nav>
  </aside>
</template>

<script setup>
const items = [
  { to: "/", label: "控制台" },
  { to: "/tasks", label: "任务管理" },
  { to: "/configs", label: "配置模板" },
  { to: "/materials", label: "素材库" },
  { to: "/source-videos", label: "源视频库" },
  { to: "/settings", label: "系统设置" },
];
</script>
