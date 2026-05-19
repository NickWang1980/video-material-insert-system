<template>
  <div class="p-4 max-w-7xl mx-auto space-y-4">
    <!-- Header -->
    <div class="flex items-start justify-between gap-4">
      <div>
        <h1 class="text-2xl font-bold dark:text-gray-100">
          {{ t("tts.page.title") }}
        </h1>
        <div class="text-sm text-gray-500 dark:text-gray-400 mt-1">
          {{ t("tts.page.subtitle") }}
        </div>
      </div>
      <el-button @click="onToggleLocale">
        {{ t("tts.page.switchLang") }}
      </el-button>
    </div>

    <!-- Model Status -->
    <el-card shadow="never" class="dark:!bg-gray-800 dark:!border-gray-700">
      <TTSModelStatus />
    </el-card>

    <!-- Main grid: input (8/12) + history (4/12) -->
    <el-row :gutter="16">
      <!-- Left: Main input -->
      <el-col :xs="24" :sm="24" :md="16" :lg="16" :xl="16">
        <el-card shadow="never" class="dark:!bg-gray-800 dark:!border-gray-700">
          <template #header>
            <div class="flex items-center justify-between">
              <span class="font-semibold dark:text-gray-100">
                {{ t("tts.input.textLabel") }}
              </span>
              <span class="text-xs text-gray-500 dark:text-gray-400">
                {{
                  t("tts.input.textCount", {
                    count: text.length,
                    max: TEXT_MAX,
                  })
                }}
              </span>
            </div>
          </template>

          <div class="space-y-4">
            <!-- Text input -->
            <el-input
              v-model="text"
              type="textarea"
              :rows="6"
              :maxlength="TEXT_MAX"
              :placeholder="t('tts.input.textPlaceholder')"
              show-word-limit
              resize="vertical"
            />

            <!-- Language + Emotion row -->
            <el-row :gutter="12">
              <el-col :xs="24" :sm="12">
                <div class="text-xs text-gray-600 dark:text-gray-300 mb-1">
                  {{ t("tts.input.language") }}
                </div>
                <el-select
                  v-model="language"
                  :placeholder="t('tts.input.language')"
                  class="!w-full"
                >
                  <el-option
                    v-for="lang in languageOptions"
                    :key="lang.code"
                    :label="lang.name || lang.code"
                    :value="lang.code"
                  />
                </el-select>
              </el-col>
              <el-col :xs="24" :sm="12">
                <div class="text-xs text-gray-600 dark:text-gray-300 mb-1">
                  {{ t("tts.input.emotion") }}
                </div>
                <el-select
                  v-model="emotion"
                  :placeholder="t('tts.input.emotion')"
                  class="!w-full"
                >
                  <el-option
                    v-for="emo in emotionOptions"
                    :key="emo.code"
                    :label="emo.name || emo.code"
                    :value="emo.code"
                  />
                </el-select>
              </el-col>
            </el-row>

            <!-- Instruct (optional) -->
            <div>
              <div class="text-xs text-gray-600 dark:text-gray-300 mb-1">
                {{ t("tts.input.instruct") }}
              </div>
              <el-input
                v-model="instruct"
                :placeholder="t('tts.input.instructPlaceholder')"
                clearable
              />
            </div>

            <!-- Speed slider -->
            <div>
              <div class="flex items-center justify-between text-xs text-gray-600 dark:text-gray-300 mb-1">
                <span>{{ t("tts.input.speed") }}</span>
                <span class="font-mono">{{ speed.toFixed(1) }}x</span>
              </div>
              <el-slider
                v-model="speed"
                :min="0.5"
                :max="2.0"
                :step="0.1"
                show-stops
              />
            </div>

            <!-- Mode tabs: clone vs preset -->
            <el-tabs v-model="activeTab" @tab-change="onTabChange">
              <el-tab-pane :label="t('tts.mode.tabClone')" name="clone">
                <div class="text-xs text-gray-500 dark:text-gray-400 mb-2">
                  {{ t("tts.mode.cloneHint") }}
                </div>
                <TTSReferenceUploader v-model="refAudioPath" />
              </el-tab-pane>
              <el-tab-pane :label="t('tts.mode.tabPreset')" name="preset">
                <div class="text-xs text-gray-500 dark:text-gray-400 mb-2">
                  {{ t("tts.mode.presetHint") }}
                </div>
                <TTSPresetVoicePicker
                  v-model="selectedVoice"
                  :voices="store.voices"
                />
              </el-tab-pane>
            </el-tabs>

            <!-- Synthesize button row -->
            <div class="flex items-center justify-between gap-3 pt-2 border-t border-gray-100 dark:border-gray-700">
              <div class="text-xs text-gray-500 dark:text-gray-400">
                <template v-if="!store.isReady">
                  {{ t("tts.modelStatus.phase.idle") }} —
                  {{ t("tts.modelStatus.loadTriggered") }}
                </template>
                <template v-else>
                  <el-tag type="success" size="small">
                    {{ t("tts.modelStatus.phase.ready") }}
                  </el-tag>
                </template>
              </div>
              <el-button
                type="primary"
                size="large"
                :loading="synthesizing"
                :disabled="synthesizing || !text.trim()"
                @click="onSynthesize"
              >
                {{
                  synthesizing
                    ? t("tts.input.synthesizing")
                    : t("tts.input.synthesize")
                }}
              </el-button>
            </div>

            <!-- Error message -->
            <el-alert
              v-if="errorMsg"
              :title="t('tts.common.error', { msg: errorMsg })"
              type="error"
              show-icon
              :closable="true"
              @close="errorMsg = ''"
            />
          </div>
        </el-card>

        <!-- Result area -->
        <el-card
          shadow="never"
          class="mt-4 dark:!bg-gray-800 dark:!border-gray-700"
        >
          <template #header>
            <span class="font-semibold dark:text-gray-100">
              {{ t("tts.result.title") }}
            </span>
          </template>
          <div v-if="store.lastResult">
            <TTSAudioPlayer
              :audio-url="store.lastResult?.audio_url"
              :filename="resultFilename"
              :duration="store.lastResult?.duration_sec"
              :show-save-button="true"
              @save-as-material="onSaveAsMaterial"
            />
          </div>
          <div
            v-else
            class="text-sm text-gray-400 dark:text-gray-500 py-6 text-center"
          >
            {{ t("tts.result.empty") }}
          </div>
        </el-card>
      </el-col>

      <!-- Right: History -->
      <el-col :xs="24" :sm="24" :md="8" :lg="8" :xl="8">
        <el-card shadow="never" class="dark:!bg-gray-800 dark:!border-gray-700">
          <template #header>
            <span class="font-semibold dark:text-gray-100">
              {{ t("tts.history.title") }}
            </span>
          </template>
          <TTSHistoryList @reuse="onReuseHistory" @play="onPlayHistory" />
        </el-card>
      </el-col>
    </el-row>

    <!-- Batch panel (collapse) -->
    <el-card shadow="never" class="dark:!bg-gray-800 dark:!border-gray-700">
      <el-collapse v-model="batchCollapse">
        <el-collapse-item :title="t('tts.batch.title')" name="batch">
          <TTSBatchPanel />
        </el-collapse-item>
      </el-collapse>
    </el-card>

    <!-- Save to Material library dialog -->
    <el-dialog
      v-model="saveDialogVisible"
      :title="t('tts.saveToMaterial.title')"
      width="480"
      :close-on-click-modal="false"
    >
      <el-form
        v-loading="treeLoading"
        label-position="top"
        size="default"
      >
        <el-form-item :label="t('tts.saveToMaterial.selectProduct')">
          <el-select
            v-model="selectedProductId"
            :placeholder="t('tts.saveToMaterial.selectProduct')"
            clearable
            class="!w-full"
            @change="onProductChange"
          >
            <el-option
              v-for="p in productOptions"
              :key="p.id"
              :label="p.name"
              :value="p.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item
          v-if="selectedProductId"
          :label="t('tts.saveToMaterial.selectScript')"
        >
          <el-select
            v-model="selectedScriptId"
            :placeholder="t('tts.saveToMaterial.selectScript')"
            clearable
            class="!w-full"
          >
            <el-option
              v-for="s in scriptOptions"
              :key="s.id"
              :label="s.name"
              :value="s.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('tts.saveToMaterial.newFileName')">
          <el-input v-model="saveFilename" placeholder="tts-result.wav" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="saveDialogVisible = false">
          {{ t("tts.common.cancel") }}
        </el-button>
        <el-button
          type="primary"
          :loading="saving"
          @click="onConfirmSaveToMaterial"
        >
          {{ t("tts.saveToMaterial.submit") }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from "vue";
import { useI18n } from "vue-i18n";
import { ElMessage } from "element-plus";

import { useTTSStore } from "../store/modules/tts";
import { toggleLocale } from "../locale";
import * as ttsApi from "../api/tts";
import { getMaterialTree, uploadMaterials } from "../api/material";

import TTSModelStatus from "../components/tts/TTSModelStatus.vue";
import TTSReferenceUploader from "../components/tts/TTSReferenceUploader.vue";
import TTSPresetVoicePicker from "../components/tts/TTSPresetVoicePicker.vue";
import TTSAudioPlayer from "../components/tts/TTSAudioPlayer.vue";
import TTSBatchPanel from "../components/tts/TTSBatchPanel.vue";
import TTSHistoryList from "../components/tts/TTSHistoryList.vue";

const store = useTTSStore();
const { t } = useI18n();

// ---- Form state ----
const text = ref("");
const language = ref("auto");
const emotion = ref("neutral");
const instruct = ref("");
const speed = ref(1.0);
const refAudioPath = ref(""); // 声音克隆模式
const selectedVoice = ref(""); // 预设音色模式
const activeTab = ref("clone"); // "clone" | "preset"
const synthesizing = ref(false);
const errorMsg = ref("");
const batchCollapse = ref([]); // 默认折叠

const TEXT_MAX = 5000;

// ---- Computed enum options w/ fallback so the dropdown isn't empty if backend hasn't responded yet ----
const languageOptions = computed(() => {
  if (Array.isArray(store.languages) && store.languages.length > 0) {
    return store.languages;
  }
  // Fallback uses the long names that qwen_tts actually expects (后端 LANGUAGE_ALIASES
  // also兜底 zh/en，但这里直接用 canonical names，保证 fallback 与 fetchEnums 后一致)
  return [
    { code: "auto", name: "auto" },
    { code: "Chinese", name: "Chinese" },
    { code: "English", name: "English" },
  ];
});

const emotionOptions = computed(() => {
  if (Array.isArray(store.emotions) && store.emotions.length > 0) {
    return store.emotions;
  }
  return [
    { code: "neutral", name: "neutral" },
    { code: "happy", name: "happy" },
    { code: "sad", name: "sad" },
    { code: "angry", name: "angry" },
  ];
});

const resultFilename = computed(() => {
  const ts = store.lastResult?.ts;
  if (!ts) return "tts-result.wav";
  const d = new Date(ts);
  const pad = (n) => String(n).padStart(2, "0");
  return `tts-${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}.wav`;
});

// ---- Lifecycle ----
// 在父页面也持有一份 polling 引用计数，这样即使 TTSModelStatus 子组件挂卸时序异常，
// 父页面整体卸载时也能保证 store.stopPolling 把引用清到 0、真正关掉 setInterval。
onMounted(async () => {
  try {
    await store.fetchEnums();
  } catch (e) {
    // 不阻塞页面加载，下拉用 fallback
    // eslint-disable-next-line no-console
    console.warn("[TTSStudio] fetchEnums failed:", e);
  }
  try {
    await store.fetchStatus();
  } catch {
    // ignore - TTSModelStatus will surface this
  }
  // 持有 polling 引用，与下方 onBeforeUnmount 中的 stopPolling 配对
  store.startPolling(2000);
});

onBeforeUnmount(() => {
  // 仅释放本页面持有的引用；子组件自己也会释放各自的引用，
  // 当所有引用清零后 store 才会真正 clearInterval。
  store.stopPolling();
});

// ---- Handlers ----
function onToggleLocale() {
  toggleLocale();
}

function onTabChange(name) {
  // 切换 Tab 时清掉另一边的参数，避免 stale
  if (name === "clone") {
    selectedVoice.value = "";
  } else if (name === "preset") {
    refAudioPath.value = "";
  }
}

async function onSynthesize() {
  if (!text.value.trim()) {
    ElMessage.warning(t("tts.input.textPlaceholder"));
    return;
  }
  synthesizing.value = true;
  errorMsg.value = "";
  try {
    const payload = {
      text: text.value,
      language: language.value,
      emotion: emotion.value,
      instruct: instruct.value || undefined,
      speed: Number(speed.value),
    };
    if (activeTab.value === "preset" && selectedVoice.value) {
      payload.voice = selectedVoice.value;
    } else if (activeTab.value === "clone" && refAudioPath.value) {
      payload.ref_audio = refAudioPath.value;
    }
    await store.synthesize(payload);
    ElMessage.success(t("tts.result.title"));
  } catch (e) {
    errorMsg.value = e?.message || String(e);
    ElMessage.error(t("tts.common.error", { msg: errorMsg.value }));
  } finally {
    synthesizing.value = false;
  }
}

function onReuseHistory(item) {
  if (!item) return;
  text.value = item.text || "";
  language.value = item.language || "auto";
  emotion.value = item.emotion || "neutral";
  instruct.value = item.instruct || "";
  speed.value = typeof item.speed === "number" ? item.speed : 1.0;
  if (item.voice) {
    activeTab.value = "preset";
    selectedVoice.value = item.voice;
    refAudioPath.value = "";
  } else {
    activeTab.value = "clone";
    refAudioPath.value = item.ref_audio || "";
    selectedVoice.value = "";
  }
  ElMessage.info(t("tts.history.reuse"));
}

function onPlayHistory(item) {
  if (!item) return;
  // 把历史项设为 lastResult，让 TTSAudioPlayer 直接展示
  store.lastResult = { ...item };
}

// ---- Save to Material library (Step 5 联动) ----
const saveDialogVisible = ref(false);
const materialTree = ref({ products: [] });
const selectedProductId = ref(null);
const selectedScriptId = ref(null);
const saveFilename = ref("");
const saving = ref(false);
const treeLoading = ref(false);

const productOptions = computed(() =>
  Array.isArray(materialTree.value?.products) ? materialTree.value.products : []
);

const scriptOptions = computed(() => {
  const p = productOptions.value.find((x) => x.id === selectedProductId.value);
  return Array.isArray(p?.scripts) ? p.scripts : [];
});

async function onSaveAsMaterial() {
  if (!store.lastResult?.audio_url) {
    ElMessage.warning(t("tts.result.empty"));
    return;
  }
  saveFilename.value = resultFilename.value;
  saveDialogVisible.value = true;
  if (productOptions.value.length === 0) {
    treeLoading.value = true;
    try {
      const tree = await getMaterialTree();
      materialTree.value = tree || { products: [] };
    } catch (e) {
      ElMessage.error(
        t("tts.saveToMaterial.failed", { msg: e?.message || String(e) })
      );
    } finally {
      treeLoading.value = false;
    }
  }
}

function onProductChange() {
  selectedScriptId.value = null;
}

async function onConfirmSaveToMaterial() {
  if (!store.lastResult?.audio_url) return;
  if (selectedProductId.value && !selectedScriptId.value) {
    ElMessage.warning(t("tts.saveToMaterial.noFolder"));
    return;
  }
  saving.value = true;
  try {
    const wavUrl = ttsApi.getTTSAudioUrl(store.lastResult.audio_url);
    const resp = await fetch(wavUrl);
    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}`);
    }
    const blob = await resp.blob();
    const finalName = (saveFilename.value || resultFilename.value).trim();
    const safeName = finalName.endsWith(".wav") ? finalName : `${finalName}.wav`;
    const file = new File([blob], safeName, { type: "audio/wav" });
    const meta = selectedScriptId.value
      ? { library_kind: "product", script_folder_id: selectedScriptId.value }
      : { library_kind: "unfiled" };
    const result = await uploadMaterials([file], meta);
    const failedList = Array.isArray(result?.failed) ? result.failed : [];
    if (failedList.length > 0) {
      throw new Error(failedList[0]?.reason || "upload failed");
    }
    ElMessage.success(t("tts.saveToMaterial.success"));
    saveDialogVisible.value = false;
  } catch (e) {
    ElMessage.error(
      t("tts.saveToMaterial.failed", { msg: e?.message || String(e) })
    );
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped>
/* 让 collapse header 在暗色下也清晰 */
:deep(.el-collapse-item__header) {
  font-weight: 600;
}
</style>
