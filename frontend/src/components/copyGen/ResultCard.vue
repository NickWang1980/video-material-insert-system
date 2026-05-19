<template>
  <el-card
    shadow="never"
    class="copy-gen-result-card dark:!bg-gray-800 dark:!border-gray-700"
  >
    <template #header>
      <div class="flex items-center justify-between flex-wrap gap-2">
        <div class="flex items-center gap-3">
          <el-tag type="primary" effect="dark" size="small">
            {{ t("copyGen.result.versionTag", { index: index + 1 }) }}
          </el-tag>
          <span class="text-xs text-gray-500 dark:text-gray-400">
            {{
              t("copyGen.result.wordCount", { count: version?.word_count ?? 0 })
            }}
          </span>
          <span
            v-if="modelUsed"
            class="text-xs text-gray-400 dark:text-gray-500"
          >
            {{ modelUsed }}
          </span>
          <span
            v-if="elapsedSec != null"
            class="text-xs text-gray-400 dark:text-gray-500"
          >
            {{ elapsedSec.toFixed(1) }}s
          </span>
        </div>
        <div class="flex items-center gap-2">
          <el-button size="small" @click="onCopyPlain">
            {{ t("copyGen.result.copyPlain") }}
          </el-button>
          <el-button size="small" @click="onCopyTTS">
            {{ t("copyGen.result.copyTTS") }}
          </el-button>
          <el-button size="small" @click="showPromptDialog = true">
            {{ t("copyGen.result.viewPrompt") }}
          </el-button>
          <el-button
            size="small"
            type="primary"
            @click="emit('send-tts', version)"
          >
            {{ t("copyGen.result.sendTTS") }}
          </el-button>
        </div>
      </div>
    </template>

    <!-- Body: paragraph content -->
    <div
      class="whitespace-pre-wrap text-sm text-gray-800 dark:text-gray-200 leading-relaxed"
    >
      {{ version?.content || "" }}
    </div>

    <!-- Voice lines -->
    <div
      v-if="voiceLines.length > 0"
      class="mt-4 border-t border-gray-100 dark:border-gray-700 pt-3"
    >
      <div
        class="text-xs text-gray-500 dark:text-gray-400 mb-2 flex items-center gap-2"
      >
        <span class="font-semibold">
          {{ t("copyGen.result.voiceLinesTitle") }}
        </span>
        <span>
          {{ t("copyGen.result.voiceLinesCount", { count: voiceLines.length }) }}
        </span>
      </div>
      <div class="flex flex-col gap-2">
        <div
          v-for="(line, lineIdx) in voiceLines"
          :key="lineIdx"
          class="rounded-md border border-gray-200 dark:border-gray-700 px-3 py-2 bg-gray-50 dark:bg-gray-900"
        >
          <div class="text-sm text-gray-800 dark:text-gray-200 break-words">
            {{ line.content }}
          </div>
          <div class="mt-1 flex items-center gap-2 flex-wrap text-xs">
            <el-tag size="small" type="info" effect="plain">
              {{ line.emotion || t("copyGen.result.emotionNeutral") }}
            </el-tag>
            <el-tag size="small" type="warning" effect="plain">
              x{{ line.speed || "1.0" }}
            </el-tag>
          </div>
        </div>
      </div>
    </div>

    <!-- Prompt dialog -->
    <el-dialog
      v-model="showPromptDialog"
      :title="t('copyGen.result.viewPrompt')"
      width="640"
    >
      <pre
        class="whitespace-pre-wrap text-xs text-gray-700 dark:text-gray-300 max-h-96 overflow-y-auto bg-gray-50 dark:bg-gray-900 p-3 rounded"
      >{{ promptText }}</pre>
      <template #footer>
        <el-button @click="showPromptDialog = false">
          {{ t("copyGen.common.close") }}
        </el-button>
        <el-button type="primary" @click="onCopyPrompt">
          {{ t("copyGen.common.copy") }}
        </el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { computed, ref } from "vue";
import { ElMessage } from "element-plus";
import { useI18n } from "vue-i18n";

const props = defineProps({
  version: { type: Object, required: true },
  index: { type: Number, default: 0 },
  elapsedSec: { type: Number, default: null },
  modelUsed: { type: String, default: "" },
  promptUsed: { type: String, default: "" },
});
const emit = defineEmits(["send-tts"]);
const { t } = useI18n();

const showPromptDialog = ref(false);

const voiceLines = computed(() =>
  Array.isArray(props.version?.voice_lines) ? props.version.voice_lines : []
);

const promptText = computed(() => {
  if (props.promptUsed) return props.promptUsed;
  return t("copyGen.result.promptUnavailable");
});

async function copyText(text, successKey) {
  try {
    await navigator.clipboard.writeText(text);
    ElMessage.success(t(successKey));
  } catch {
    // Fallback: textarea trick
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    try {
      document.execCommand("copy");
      ElMessage.success(t(successKey));
    } catch {
      ElMessage.error(t("copyGen.common.copyFailed"));
    } finally {
      document.body.removeChild(ta);
    }
  }
}

function onCopyPlain() {
  copyText(props.version?.content || "", "copyGen.result.copiedPlain");
}

function onCopyTTS() {
  const text =
    props.version?.qwen3_tts_text ||
    voiceLines.value
      .map(
        (l) =>
          `${l.content || ""}|${l.emotion || ""}|${l.speed || ""}`
      )
      .join("\n");
  copyText(text, "copyGen.result.copiedTTS");
}

function onCopyPrompt() {
  copyText(promptText.value, "copyGen.result.copiedPrompt");
}
</script>
