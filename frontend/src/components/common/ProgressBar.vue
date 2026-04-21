<template>
  <div class="w-full h-2.5 rounded-full bg-gray-200 overflow-hidden">
    <div
      class="h-2.5 progress-fill transition-all duration-500"
      :class="{ 'progress-breathing': isBreathing }"
      :style="{ width: `${displayPercent}%` }"
    ></div>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  percent: { type: Number, required: true },
  status: { type: String, default: "" },
});

const safePercent = computed(() => {
  const value = Number(props.percent || 0);
  if (Number.isNaN(value)) return 0;
  return Math.max(0, Math.min(100, value));
});

const isBreathing = computed(() => {
  if (props.status) {
    return props.status === "pending" || props.status === "processing";
  }
  return safePercent.value < 100;
});

const displayPercent = computed(() => {
  if (isBreathing.value && safePercent.value < 3) {
    return 3;
  }
  return safePercent.value;
});
</script>
