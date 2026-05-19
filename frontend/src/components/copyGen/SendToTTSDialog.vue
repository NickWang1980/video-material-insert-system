<template>
  <el-dialog
    :model-value="modelValue"
    :title="t('copyGen.sendTTS.title')"
    width="640"
    :close-on-click-modal="false"
    @update:model-value="(v) => emit('update:modelValue', v)"
    @close="onClose"
  >
    <div class="space-y-3">
      <el-alert
        v-if="!ttsStore.isReady"
        :title="t('copyGen.sendTTS.modelNotReady')"
        type="warning"
        :closable="false"
        show-icon
      />

      <!-- Voice mode -->
      <div>
        <div class="text-xs text-gray-600 dark:text-gray-300 mb-1">
          {{ t("copyGen.sendTTS.modeLabel") }}
        </div>
        <el-radio-group v-model="voiceMode" :disabled="running">
          <el-radio value="preset">
            {{ t("copyGen.sendTTS.modePreset") }}
          </el-radio>
          <el-radio value="clone">
            {{ t("copyGen.sendTTS.modeClone") }}
          </el-radio>
        </el-radio-group>
      </div>

      <!-- Voice selector -->
      <div v-if="voiceMode === 'preset'">
        <div class="text-xs text-gray-600 dark:text-gray-300 mb-1">
          {{ t("copyGen.sendTTS.voiceLabel") }}
        </div>
        <el-select
          v-model="selectedVoice"
          :placeholder="t('copyGen.sendTTS.voicePlaceholder')"
          class="!w-full"
          :disabled="running"
          filterable
        >
          <el-option
            v-for="v in voiceList"
            :key="v.code"
            :label="`${v.code}${v.description ? ' — ' + v.description : ''}`"
            :value="v.code"
          />
        </el-select>
      </div>
      <div v-else>
        <div class="text-xs text-gray-600 dark:text-gray-300 mb-1">
          {{ t("copyGen.sendTTS.refAudioLabel") }}
        </div>
        <el-upload
          accept="audio/*"
          :auto-upload="false"
          :show-file-list="false"
          :multiple="false"
          :disabled="running || uploading"
          :on-change="onRefFileChange"
        >
          <el-button :disabled="running || uploading" size="small">
            {{
              uploading
                ? t("copyGen.sendTTS.uploading")
                : t("copyGen.sendTTS.uploadRef")
            }}
          </el-button>
        </el-upload>
        <div class="text-xs text-gray-500 mt-1">
          <span v-if="refAudioPath">{{ refAudioName }}</span>
          <span v-else class="text-gray-400">
            {{ t("copyGen.sendTTS.noRefAudio") }}
          </span>
        </div>
      </div>

      <!-- Lines checklist -->
      <div>
        <div class="flex items-center justify-between mb-1">
          <span class="text-xs text-gray-600 dark:text-gray-300">
            {{ t("copyGen.sendTTS.linesLabel", { count: voiceLines.length }) }}
          </span>
          <div class="flex items-center gap-2">
            <el-button
              size="small"
              text
              :disabled="running"
              @click="selectAll(true)"
            >
              {{ t("copyGen.common.selectAll") }}
            </el-button>
            <el-button
              size="small"
              text
              :disabled="running"
              @click="selectAll(false)"
            >
              {{ t("copyGen.common.deselectAll") }}
            </el-button>
          </div>
        </div>
        <div
          class="border rounded-md max-h-72 overflow-y-auto p-2 bg-gray-50 dark:bg-gray-900 dark:border-gray-700"
        >
          <div
            v-for="(line, i) in lineItems"
            :key="i"
            class="flex items-start gap-2 py-1.5 border-b last:border-b-0 border-gray-200 dark:border-gray-700"
          >
            <el-checkbox
              v-model="line.selected"
              :disabled="running"
            />
            <div class="flex-1 text-sm">
              <div class="text-gray-800 dark:text-gray-200 break-words">
                {{ line.content }}
              </div>
              <div class="text-xs text-gray-500 mt-0.5 flex items-center gap-2">
                <el-tag size="small" type="info" effect="plain">
                  {{ line.emotion || t("copyGen.result.emotionNeutral") }}
                </el-tag>
                <el-tag size="small" type="warning" effect="plain">
                  x{{ line.speed || "1.0" }}
                </el-tag>
                <el-tag
                  v-if="line.status"
                  size="small"
                  :type="statusTag(line.status)"
                  effect="plain"
                >
                  {{ statusLabel(line.status) }}
                </el-tag>
                <span v-if="line.error" class="text-red-500">
                  {{ line.error }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Progress -->
      <div v-if="running || doneCount > 0">
        <el-progress
          :percentage="progressPercent"
          :status="
            running
              ? ''
              : doneCount === selectedCount && selectedCount > 0
                ? 'success'
                : ''
          "
        />
        <div class="text-xs text-gray-500 mt-1">
          {{
            t("copyGen.sendTTS.progress", {
              done: doneCount,
              total: selectedCount,
            })
          }}
        </div>
      </div>
    </div>

    <template #footer>
      <el-button @click="onClose" :disabled="running">
        {{ t("copyGen.common.close") }}
      </el-button>
      <el-button
        v-if="completed && !running"
        type="success"
        @click="goToTTSStudio"
      >
        {{ t("copyGen.sendTTS.gotoStudio") }}
      </el-button>
      <el-button
        type="primary"
        :loading="running"
        :disabled="running || selectedCount === 0 || !canStart"
        @click="onStart"
      >
        {{ running ? t("copyGen.sendTTS.synthesizing") : t("copyGen.sendTTS.start") }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch, onMounted } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { useI18n } from "vue-i18n";
import { useTTSStore } from "../../store/modules/tts";
import * as ttsApi from "../../api/tts";

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  version: { type: Object, default: null },
});
const emit = defineEmits(["update:modelValue"]);
const { t } = useI18n();
const ttsStore = useTTSStore();
const router = useRouter();

const voiceMode = ref("preset");
const selectedVoice = ref("");
const refAudioPath = ref("");
const refAudioName = ref("");
const uploading = ref(false);

const lineItems = ref([]); // [{ content, emotion, speed, selected, status, error, audio_url }]
const running = ref(false);
const completed = ref(false);
let abortController = null;

const voiceList = computed(() =>
  Array.isArray(ttsStore.voices) ? ttsStore.voices : []
);

const voiceLines = computed(() =>
  Array.isArray(props.version?.voice_lines) ? props.version.voice_lines : []
);

const selectedCount = computed(
  () => lineItems.value.filter((l) => l.selected).length
);

const doneCount = computed(
  () =>
    lineItems.value.filter(
      (l) => l.selected && (l.status === "done" || l.status === "error")
    ).length
);

const progressPercent = computed(() => {
  if (selectedCount.value === 0) return 0;
  return Math.round((doneCount.value / selectedCount.value) * 100);
});

const canStart = computed(() => {
  if (voiceMode.value === "preset") return !!selectedVoice.value;
  return !!refAudioPath.value;
});

// Re-init lineItems whenever dialog opens
watch(
  () => [props.modelValue, props.version],
  ([open]) => {
    if (open) {
      lineItems.value = voiceLines.value.map((l) => ({
        content: l.content || "",
        emotion: l.emotion || "",
        speed: l.speed || "1.0",
        original_text: l.original_text || "",
        selected: true,
        status: "",
        error: "",
        audio_url: "",
      }));
      running.value = false;
      completed.value = false;
    }
  },
  { immediate: true }
);

onMounted(async () => {
  try {
    if (ttsStore.voices.length === 0) {
      await ttsStore.fetchEnums();
    }
  } catch {
    // ignore - dialog still opens, user just won't see voices
  }
});

function selectAll(v) {
  lineItems.value.forEach((l) => {
    l.selected = !!v;
  });
}

async function onRefFileChange(uploadFile) {
  const raw = uploadFile?.raw;
  if (!raw) return;
  uploading.value = true;
  try {
    const result = await ttsStore.uploadReference(raw);
    const refPath =
      typeof result === "string" ? result : result?.ref_audio_path || "";
    if (!refPath) throw new Error("empty ref_audio_path");
    refAudioPath.value = refPath;
    refAudioName.value = uploadFile.name;
    ElMessage.success(t("copyGen.sendTTS.refUploadSuccess"));
  } catch (e) {
    ElMessage.error(
      t("copyGen.common.errorMsg", { msg: e?.message || String(e) })
    );
  } finally {
    uploading.value = false;
  }
}

function buildInstruct(line) {
  // Compose `emotion, speed` instruct (skip empties cleanly)
  const parts = [];
  if (line.emotion) parts.push(line.emotion);
  if (line.speed) parts.push(line.speed);
  return parts.join(", ");
}

function parseSpeedNumber(s) {
  if (typeof s === "number") return s;
  if (!s) return 1.0;
  const m = String(s).match(/[-+]?\d*\.?\d+/);
  return m ? Math.max(0.5, Math.min(2.0, parseFloat(m[0]))) : 1.0;
}

async function onStart() {
  if (running.value) return;
  if (selectedCount.value === 0) {
    ElMessage.warning(t("copyGen.sendTTS.noLinesSelected"));
    return;
  }
  if (!canStart.value) {
    ElMessage.warning(
      voiceMode.value === "preset"
        ? t("copyGen.sendTTS.selectVoiceFirst")
        : t("copyGen.sendTTS.uploadRefFirst")
    );
    return;
  }
  running.value = true;
  completed.value = false;
  try {
    for (let i = 0; i < lineItems.value.length; i++) {
      const line = lineItems.value[i];
      if (!line.selected) continue;
      if (line.status === "done") continue; // resume
      line.status = "processing";
      line.error = "";
      abortController = new AbortController();
      try {
        const payload = {
          text: line.content,
          language: "auto",
          emotion: "neutral",
          speed: parseSpeedNumber(line.speed),
        };
        const instruct = buildInstruct(line);
        if (instruct) payload.instruct = instruct;
        if (voiceMode.value === "preset") {
          payload.voice = selectedVoice.value;
        } else {
          payload.ref_audio = refAudioPath.value;
        }
        const resp = await ttsApi.synthesizeTTS(payload, {
          signal: abortController.signal,
        });
        line.audio_url = resp?.audio_url || "";
        line.status = "done";
      } catch (e) {
        const aborted =
          e?.name === "CanceledError" ||
          e?.code === "ERR_CANCELED" ||
          e?.message === "canceled";
        if (aborted) {
          line.status = "";
          line.error = "";
          break;
        }
        line.status = "error";
        line.error = e?.message || String(e);
      } finally {
        abortController = null;
      }
    }
    completed.value = true;
    const okCount = lineItems.value.filter((l) => l.status === "done").length;
    if (okCount > 0) {
      ElMessage.success(
        t("copyGen.sendTTS.doneToast", { count: okCount })
      );
    }
  } finally {
    running.value = false;
  }
}

function onClose() {
  if (running.value && abortController) {
    try {
      abortController.abort();
    } catch {
      // ignore
    }
  }
  emit("update:modelValue", false);
}

function goToTTSStudio() {
  emit("update:modelValue", false);
  router.push("/tts");
}

function statusLabel(s) {
  switch (s) {
    case "processing":
      return t("copyGen.sendTTS.statusProcessing");
    case "done":
      return t("copyGen.sendTTS.statusDone");
    case "error":
      return t("copyGen.sendTTS.statusError");
    default:
      return t("copyGen.sendTTS.statusPending");
  }
}

function statusTag(s) {
  switch (s) {
    case "done":
      return "success";
    case "processing":
      return "warning";
    case "error":
      return "danger";
    default:
      return "info";
  }
}
</script>
