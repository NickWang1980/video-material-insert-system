<template>
  <div v-if="resolvedUrl" class="tts-audio-player flex flex-col gap-2">
    <div class="flex items-center justify-between">
      <span class="text-sm font-medium text-gray-700">{{ t("tts.result.title") }}</span>
      <span v-if="duration > 0" class="text-xs text-gray-500">
        {{ t("tts.result.duration", { seconds: duration.toFixed(1) }) }}
      </span>
    </div>
    <audio
      :src="resolvedUrl"
      controls
      preload="auto"
      class="w-full"
    />
    <div class="flex items-center gap-2">
      <el-link
        type="primary"
        :href="resolvedUrl"
        :download="downloadName"
        :underline="false"
      >
        <el-icon class="mr-1"><Download /></el-icon>
        {{ t("tts.result.download") }}
      </el-link>
      <el-button
        v-if="showSaveButton"
        type="success"
        size="small"
        @click="$emit('save-as-material')"
      >
        {{ t("tts.result.saveAsMaterial") }}
      </el-button>
    </div>
  </div>
  <div v-else class="text-sm text-gray-400 italic">
    {{ t("tts.result.empty") }}
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { Download } from "@element-plus/icons-vue";
import * as ttsApi from "../../api/tts";

const props = defineProps({
  audioUrl: { type: String, default: "" },
  filename: { type: String, default: "" },
  duration: { type: Number, default: 0 },
  showSaveButton: { type: Boolean, default: false },
});

defineEmits(["save-as-material"]);

const { t } = useI18n();

const resolvedUrl = computed(() =>
  props.audioUrl ? ttsApi.getTTSAudioUrl(props.audioUrl) : ""
);

const downloadName = computed(() => {
  if (props.filename) return props.filename;
  const m = props.audioUrl ? props.audioUrl.match(/\/([^/?]+\.wav)$/i) : null;
  return m ? m[1] : "tts.wav";
});
</script>

<style scoped>
.tts-audio-player audio {
  outline: none;
}
</style>
