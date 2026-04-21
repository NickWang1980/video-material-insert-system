<template>
  <el-upload
    drag
    :auto-upload="false"
    :multiple="multiple"
    :accept="accept"
    :limit="limit"
    :on-change="onChange"
    class="w-full"
  >
    <div class="p-6 text-center">
      <div class="font-medium">{{ title }}</div>
      <div class="text-sm text-gray-500 mt-1">{{ hint }}</div>
    </div>
  </el-upload>
</template>

<script setup>
const props = defineProps({
  title: { type: String, required: true },
  hint: { type: String, default: "" },
  multiple: { type: Boolean, default: false },
  accept: { type: String, default: "" },
  limit: { type: Number, default: 20 },
});

const emit = defineEmits(["update:files"]);

function onChange(file, fileList) {
  emit(
    "update:files",
    fileList.map((x) => x.raw).filter(Boolean)
  );
}
</script>
