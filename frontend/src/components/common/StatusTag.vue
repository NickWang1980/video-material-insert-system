<template>
  <span class="px-2 py-1 rounded-full text-xs text-white" :class="cls">{{ text }}</span>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  status: { type: String, required: true },
});

const cls = computed(() => {
  if (props.status === "completed") return "bg-green-500";
  if (props.status === "processing") return "bg-blue-500";
  if (props.status === "stopped") return "bg-amber-500";
  if (props.status === "failed") return "bg-red-500";
  return "bg-gray-500";
});

const text = computed(() => {
  const map = {
    pending: "待处理",
    processing: "处理中",
    stopped: "已停止",
    completed: "已完成",
    failed: "失败",
  };
  return map[props.status] || props.status;
});
</script>
