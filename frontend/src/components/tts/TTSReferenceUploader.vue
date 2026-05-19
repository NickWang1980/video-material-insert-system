<template>
  <div class="tts-reference-uploader space-y-2">
    <el-upload
      drag
      accept="audio/*"
      :auto-upload="false"
      :show-file-list="false"
      :multiple="false"
      :disabled="uploading"
      :on-change="onFileChange"
      class="w-full"
    >
      <div class="p-6 text-center">
        <el-icon class="text-2xl text-gray-400">
          <i class="el-icon-upload" />
        </el-icon>
        <div class="text-sm text-gray-500 mt-1">
          {{ t("tts.reference.uploadHint") }}
        </div>
      </div>
    </el-upload>

    <div class="flex items-center justify-between text-sm">
      <div class="text-gray-600">
        <template v-if="displayName">
          {{ t("tts.reference.uploaded", { name: displayName }) }}
        </template>
        <template v-else>
          <span class="text-gray-400">
            {{ t("tts.reference.noFile") }}
          </span>
        </template>
      </div>
      <el-button
        v-if="props.modelValue || localFileName"
        type="default"
        size="small"
        :disabled="uploading"
        @click="onClear"
      >
        {{ t("tts.common.close") }}
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { useI18n } from "vue-i18n";
import { useTTSStore } from "../../store/modules/tts";

const props = defineProps({
  modelValue: { type: String, default: "" },
});
const emit = defineEmits(["update:modelValue"]);

const store = useTTSStore();
const { t } = useI18n();

const uploading = ref(false);
const localFileName = ref("");

// 当外部清空 modelValue 时同步本地名称
watch(
  () => props.modelValue,
  (val) => {
    if (!val) {
      localFileName.value = "";
    }
  }
);

const displayName = computed(() => {
  if (localFileName.value) return localFileName.value;
  if (props.modelValue) {
    // 从路径中解析文件名（兼容正反斜杠）
    const parts = String(props.modelValue).split(/[\\/]/);
    return parts[parts.length - 1] || props.modelValue;
  }
  return "";
});

async function onFileChange(file) {
  if (!file || !file.raw) return;
  uploading.value = true;
  try {
    const result = await store.uploadReference(file.raw);
    const refPath =
      typeof result === "string" ? result : result?.ref_audio_path || "";
    if (!refPath) {
      throw new Error("empty ref_audio_path");
    }
    emit("update:modelValue", refPath);
    localFileName.value = file.name;
    ElMessage.success(t("tts.reference.uploadSuccess"));
  } catch (e) {
    // eslint-disable-next-line no-console
    console.warn("[TTSReferenceUploader] upload failed", e);
    ElMessage.error(t("tts.reference.uploadFailed"));
  } finally {
    uploading.value = false;
  }
}

function onClear() {
  emit("update:modelValue", "");
  localFileName.value = "";
}
</script>
