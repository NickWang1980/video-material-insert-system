<template>
  <el-card class="tts-history-list" shadow="never">
    <template #header>
      <div class="flex items-center justify-between">
        <span class="font-medium">{{ t("tts.history.title") }}</span>
        <el-popconfirm
          :title="t('tts.history.confirmClear')"
          :confirm-button-text="t('tts.common.confirm')"
          :cancel-button-text="t('tts.common.cancel')"
          @confirm="onClear"
        >
          <template #reference>
            <el-button
              size="small"
              type="danger"
              text
              :disabled="store.history.length === 0"
            >
              {{ t("tts.history.clear") }}
            </el-button>
          </template>
        </el-popconfirm>
      </div>
    </template>

    <div
      v-if="store.history.length === 0"
      class="text-sm text-gray-400 italic py-6 text-center"
    >
      {{ t("tts.history.empty") }}
    </div>

    <div
      v-else
      class="history-scroll flex flex-col gap-2"
      style="max-height: 600px; overflow-y: auto;"
    >
      <div
        v-for="(item, index) in store.history"
        :key="`${item.ts}-${index}`"
        class="history-item border rounded p-2 flex flex-col gap-1 bg-white hover:bg-gray-50"
      >
        <div class="text-sm text-gray-800 break-words">
          {{ truncate(item.text, 60) }}
        </div>
        <div class="text-xs text-gray-500 flex flex-wrap gap-x-3 gap-y-1">
          <span v-if="item.language">{{ item.language }}</span>
          <span v-if="item.emotion">{{ item.emotion }}</span>
          <span v-if="typeof item.speed === 'number'">x{{ item.speed }}</span>
          <span v-if="item.voice">voice: {{ item.voice }}</span>
          <span v-else-if="item.ref_audio">ref</span>
        </div>
        <div class="text-xs text-gray-400">
          {{ t("tts.history.playedAt", { time: formatTime(item.ts) }) }}
        </div>
        <div class="flex items-center gap-2 mt-1">
          <el-button
            size="small"
            type="primary"
            text
            :disabled="!item.audio_url"
            @click="emit('play', item)"
          >
            {{ t("tts.result.play") }}
          </el-button>
          <el-button
            size="small"
            type="primary"
            text
            @click="emit('reuse', item)"
          >
            {{ t("tts.history.reuse") }}
          </el-button>
          <el-button
            size="small"
            type="danger"
            text
            @click="onDelete(index)"
          >
            {{ t("tts.history.delete") }}
          </el-button>
        </div>
      </div>
    </div>
  </el-card>
</template>

<script setup>
import { useTTSStore } from "../../store/modules/tts";
import { useI18n } from "vue-i18n";
import { ElMessage } from "element-plus";

const store = useTTSStore();
const emit = defineEmits(["reuse", "play"]);
const { t } = useI18n();

function onClear() {
  store.clearHistory();
  ElMessage.success(t("tts.history.clear"));
}

function onDelete(index) {
  store.deleteHistoryAt(index);
}

function truncate(text, maxLen) {
  if (!text) return "";
  return text.length > maxLen ? `${text.slice(0, maxLen)}…` : text;
}

function formatTime(ts) {
  if (!ts) return "";
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return String(ts);
  }
}
</script>

<style scoped>
.history-item {
  transition: background-color 0.15s ease;
}
</style>
