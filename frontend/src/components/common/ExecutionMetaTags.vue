<template>
  <div v-if="anyValue" class="flex flex-wrap items-center gap-1.5 text-xs">
    <span v-if="model" class="meta-tag">模型 {{ model }}</span>
    <span v-if="compute" class="meta-tag">精度 {{ compute }}</span>
    <span v-if="encoder" class="meta-tag">编码器 {{ encoder }}</span>
    <span v-if="resolution" class="meta-tag">尺寸 {{ resolution }}</span>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  model: { type: String, default: "" },
  compute: { type: String, default: "" },
  encoder: { type: String, default: "" },
  resolution: { type: String, default: "" },
});

const anyValue = computed(
  () => !!(props.model || props.compute || props.encoder || props.resolution)
);
</script>

<style scoped>
.meta-tag {
  padding: 2px 8px;
  border-radius: 4px;
  background: #f3f4f6;
  color: #374151;
  white-space: nowrap;
}
</style>

<style>
html.dark .meta-tag {
  background: #374151 !important;
  color: #d1d5db !important;
}
html.glass .meta-tag {
  background: rgba(255, 255, 255, 0.1) !important;
  color: rgba(255, 255, 255, 0.85) !important;
}
</style>
