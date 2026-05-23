<template>
  <div class="copy-gen-quick-generator">
    <el-row :gutter="16">
      <!-- Left: Form + results (16) -->
      <el-col :xs="24" :sm="24" :md="16" :lg="16" :xl="16">
        <!-- Empty state when no model configs -->
        <el-card
          v-if="store.modelConfigs.length === 0 && !store.loading.models"
          shadow="never"
          class="dark:!bg-gray-800 dark:!border-gray-700"
        >
          <div class="text-center py-10">
            <div class="text-base text-gray-700 dark:text-gray-200 mb-2">
              {{ t("copyGen.quickGen.noModelsTitle") }}
            </div>
            <div class="text-sm text-gray-500 dark:text-gray-400 mb-4">
              {{ t("copyGen.quickGen.noModelsHint") }}
            </div>
            <el-button type="primary" @click="emit('goto-tab', 'models')">
              {{ t("copyGen.quickGen.gotoModelsTab") }}
            </el-button>
          </div>
        </el-card>

        <!-- Main form -->
        <el-card
          v-else
          shadow="never"
          class="dark:!bg-gray-800 dark:!border-gray-700"
        >
          <template #header>
            <span class="font-semibold dark:text-gray-100">
              {{ t("copyGen.quickGen.formTitle") }}
            </span>
          </template>

          <el-form label-position="top" :model="form">
            <el-form-item :label="t('copyGen.quickGen.topic')" required>
              <el-input
                v-model="form.topic"
                type="textarea"
                :rows="3"
                :placeholder="t('copyGen.quickGen.topicPlaceholder')"
                :maxlength="500"
                show-word-limit
              />
            </el-form-item>

            <el-row :gutter="12">
              <el-col :xs="24" :sm="8">
                <el-form-item :label="t('copyGen.quickGen.platform')">
                  <el-select
                    v-model="form.platform"
                    :placeholder="t('copyGen.quickGen.platformPlaceholder')"
                    class="!w-full"
                    clearable
                  >
                    <el-option
                      v-for="p in platforms"
                      :key="p.code || p"
                      :label="p.name || p.code || p"
                      :value="p.code || p"
                    />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="8">
                <el-form-item :label="t('copyGen.quickGen.template')">
                  <el-select
                    v-model="form.template"
                    :placeholder="t('copyGen.quickGen.templatePlaceholder')"
                    class="!w-full"
                    clearable
                  >
                    <el-option
                      v-for="tmpl in templates"
                      :key="tmpl.code || tmpl"
                      :label="tmpl.name || tmpl.code || tmpl"
                      :value="tmpl.code || tmpl"
                    />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="8">
                <el-form-item :label="t('copyGen.quickGen.scriptType')">
                  <el-radio-group v-model="form.script_type">
                    <el-radio value="single">
                      {{ t("copyGen.quickGen.scriptSingle") }}
                    </el-radio>
                    <el-radio value="ab_role">
                      {{ t("copyGen.quickGen.scriptAB") }}
                    </el-radio>
                  </el-radio-group>
                </el-form-item>
              </el-col>
            </el-row>

            <el-row :gutter="12">
              <el-col :xs="12" :sm="6">
                <el-form-item :label="t('copyGen.quickGen.targetWords')">
                  <el-input-number
                    v-model="form.target_words"
                    :min="50"
                    :max="2000"
                    :step="50"
                    class="!w-full"
                  />
                </el-form-item>
              </el-col>
              <el-col :xs="12" :sm="6">
                <el-form-item :label="t('copyGen.quickGen.tolerance')">
                  <el-input-number
                    v-model="form.tolerance"
                    :min="0"
                    :max="500"
                    :step="10"
                    class="!w-full"
                  />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item :label="t('copyGen.quickGen.numVersions')">
                  <div class="flex items-center gap-3">
                    <el-slider
                      v-model="form.num_versions"
                      :min="1"
                      :max="10"
                      :step="1"
                      show-stops
                      class="flex-1"
                    />
                    <span class="text-sm font-mono w-6 text-right">
                      {{ form.num_versions }}
                    </span>
                  </div>
                </el-form-item>
              </el-col>
            </el-row>

            <el-row :gutter="12">
              <el-col :xs="24" :sm="12">
                <el-form-item :label="t('copyGen.quickGen.agent')">
                  <el-select
                    v-model="agentSelection"
                    :placeholder="
                      store.agents.length === 0
                        ? t('copyGen.quickGen.noAgents')
                        : t('copyGen.quickGen.agentPlaceholder')
                    "
                    class="!w-full"
                    clearable
                  >
                    <el-option
                      :label="t('copyGen.quickGen.noAgentOption')"
                      :value="null"
                    />
                    <el-option
                      v-for="a in store.agents"
                      :key="a.id"
                      :label="a.name"
                      :value="a.id"
                    />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item :label="t('copyGen.quickGen.modelConfig')">
                  <el-select
                    v-model="modelConfigSelection"
                    :placeholder="t('copyGen.quickGen.modelConfigPlaceholder')"
                    class="!w-full"
                    clearable
                  >
                    <el-option
                      v-for="m in store.modelConfigs"
                      :key="m.id"
                      :label="`${m.name} (${m.model_name})`"
                      :value="m.id"
                    />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>

            <el-form-item :label="t('copyGen.quickGen.extraInstructions')">
              <el-input
                v-model="form.extra_instructions"
                type="textarea"
                :rows="2"
                :placeholder="t('copyGen.quickGen.extraInstructionsPlaceholder')"
              />
            </el-form-item>

            <!-- Advanced overrides -->
            <el-collapse v-model="advancedOpen">
              <el-collapse-item
                :title="t('copyGen.quickGen.advancedTitle')"
                name="adv"
              >
                <el-row :gutter="12">
                  <el-col :span="12">
                    <el-form-item :label="t('copyGen.quickGen.temperatureOverride')">
                      <el-input-number
                        v-model="form.temperature"
                        :min="0"
                        :max="2"
                        :step="0.1"
                        class="!w-full"
                        controls-position="right"
                      />
                    </el-form-item>
                  </el-col>
                  <el-col :span="12">
                    <el-form-item :label="t('copyGen.quickGen.maxTokensOverride')">
                      <el-input-number
                        v-model="form.max_tokens"
                        :min="0"
                        :max="32000"
                        :step="256"
                        class="!w-full"
                        controls-position="right"
                      />
                    </el-form-item>
                  </el-col>
                </el-row>
                <el-form-item :label="t('copyGen.quickGen.systemPromptOverride')">
                  <el-input
                    v-model="form.system_prompt_override"
                    type="textarea"
                    :rows="3"
                    :placeholder="
                      t('copyGen.quickGen.systemPromptOverridePlaceholder')
                    "
                  />
                </el-form-item>
              </el-collapse-item>
            </el-collapse>

            <!-- Validation warning -->
            <el-alert
              v-if="!hasModel"
              :title="t('copyGen.quickGen.noModelWarning')"
              type="warning"
              :closable="false"
              show-icon
              class="!mt-2"
            />

            <!-- Action row -->
            <div
              class="flex items-center justify-between gap-3 pt-3 border-t border-gray-100 dark:border-gray-700 mt-2"
            >
              <div class="text-xs text-gray-500 dark:text-gray-400">
                <span v-if="agentSelection">
                  {{ t("copyGen.quickGen.usingAgent", { name: agentName }) }}
                </span>
                <span v-else>
                  {{ t("copyGen.quickGen.usingQuick") }}
                </span>
              </div>
              <div class="flex items-center gap-2">
                <el-button
                  v-if="store.loading.generate"
                  type="warning"
                  @click="onCancel"
                >
                  {{ t("copyGen.quickGen.cancel") }}
                </el-button>
                <el-button
                  type="primary"
                  size="large"
                  :loading="store.loading.generate"
                  :disabled="!canGenerate"
                  @click="onGenerate"
                >
                  {{
                    store.loading.generate
                      ? t("copyGen.quickGen.generating")
                      : t("copyGen.quickGen.generate")
                  }}
                </el-button>
              </div>
            </div>

            <!-- Error -->
            <el-alert
              v-if="errorMsg"
              :title="errorMsg"
              type="error"
              show-icon
              :closable="true"
              class="!mt-2"
              @close="errorMsg = ''"
            />
          </el-form>
        </el-card>

        <!-- Results -->
        <div v-if="store.lastResult" class="mt-4 space-y-3">
          <div class="text-sm text-gray-500 dark:text-gray-400">
            {{
              t("copyGen.result.summary", {
                count: versionsArr.length,
                model: store.lastResult.model_used || "",
                elapsed: (store.lastResult.elapsed_sec || 0).toFixed(1),
              })
            }}
          </div>
          <ResultCard
            v-for="(v, i) in versionsArr"
            :key="`${store.lastResult.generation_id}-${i}`"
            :version="v"
            :index="i"
            :elapsed-sec="store.lastResult.elapsed_sec"
            :model-used="store.lastResult.model_used"
            :prompt-used="store.lastResult.prompt_used || ''"
            @send-tts="onSendTTS"
          />
        </div>
      </el-col>

      <!-- Right: summary + history (8) -->
      <el-col :xs="24" :sm="24" :md="8" :lg="8" :xl="8">
        <el-card shadow="never" class="dark:!bg-gray-800 dark:!border-gray-700">
          <template #header>
            <span class="font-semibold dark:text-gray-100">
              {{ t("copyGen.quickGen.summaryTitle") }}
            </span>
          </template>
          <div class="text-sm space-y-2">
            <div class="flex items-center justify-between">
              <span class="text-gray-500 dark:text-gray-400">
                {{ t("copyGen.quickGen.agent") }}
              </span>
              <span class="dark:text-gray-200">
                {{ agentName || t("copyGen.quickGen.noAgentOption") }}
              </span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-gray-500 dark:text-gray-400">
                {{ t("copyGen.quickGen.modelConfig") }}
              </span>
              <span class="dark:text-gray-200">
                {{ modelConfigName || "—" }}
              </span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-gray-500 dark:text-gray-400">
                {{ t("copyGen.quickGen.platform") }}
              </span>
              <span class="dark:text-gray-200">
                {{ form.platform || "—" }}
              </span>
            </div>
          </div>
        </el-card>

        <el-card
          shadow="never"
          class="mt-3 dark:!bg-gray-800 dark:!border-gray-700"
        >
          <el-collapse v-model="historyCollapse">
            <el-collapse-item
              :title="t('copyGen.history.title')"
              name="history"
            >
              <HistoryList @reuse="onReuseHistory" />
            </el-collapse-item>
          </el-collapse>
        </el-card>
      </el-col>
    </el-row>

    <!-- Send to TTS dialog -->
    <SendToTTSDialog v-model="sendTTSVisible" :version="sendTTSVersion" />
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onBeforeUnmount } from "vue";
import { ElMessage } from "element-plus";
import { useI18n } from "vue-i18n";
import { useCopyGenStore } from "../../store/modules/copyGen";
import ResultCard from "./ResultCard.vue";
import HistoryList from "./HistoryList.vue";
import SendToTTSDialog from "./SendToTTSDialog.vue";

const emit = defineEmits(["goto-tab"]);
const { t } = useI18n();
const store = useCopyGenStore();

const form = reactive({
  topic: "",
  platform: "",
  template: "",
  script_type: "single",
  target_words: 300,
  tolerance: 50,
  num_versions: 3,
  extra_instructions: "",
  temperature: null,
  max_tokens: null,
  system_prompt_override: "",
});

const advancedOpen = ref([]);
const historyCollapse = ref(["history"]);
const errorMsg = ref("");
let abortController = null;

const sendTTSVisible = ref(false);
const sendTTSVersion = ref(null);

const platforms = computed(() => store.enums.platforms || []);
const templates = computed(() => store.enums.templates || []);

// Two-way bind to store-level current selections so other tabs see the same state.
const agentSelection = computed({
  get: () => store.currentAgentId,
  set: (v) => store.setCurrentAgentId(v),
});
const modelConfigSelection = computed({
  get: () => store.currentModelConfigId,
  set: (v) => store.setCurrentModelConfigId(v),
});

const agentName = computed(() => store.currentAgent?.name || "");
const modelConfigName = computed(() => {
  const m = store.currentModelConfig;
  if (!m) return "";
  return `${m.name} (${m.model_name})`;
});

// Inferred model: explicit modelConfig OR via selected agent's default model_config_id
const hasModel = computed(() => {
  if (modelConfigSelection.value) return true;
  if (agentSelection.value) {
    const a = store.agents.find((x) => x.id === agentSelection.value);
    return !!a?.model_config_id;
  }
  return false;
});

const canGenerate = computed(() => {
  return (
    !!form.topic.trim() &&
    !store.loading.generate &&
    hasModel.value
  );
});

const versionsArr = computed(() => {
  const v = store.lastResult?.versions;
  return Array.isArray(v) ? v : [];
});

// Auto-pick first model config when one exists and none selected.
watch(
  () => store.modelConfigs.length,
  (n) => {
    if (n > 0 && modelConfigSelection.value == null) {
      modelConfigSelection.value = store.modelConfigs[0].id;
    }
  },
  { immediate: true }
);

function buildPayload() {
  const payload = {
    topic: form.topic.trim(),
    platform: form.platform || null,
    template: form.template || null,
    script_type: form.script_type || "single",
    target_words: Number(form.target_words) || 300,
    tolerance: Number(form.tolerance) || 50,
    num_versions: Number(form.num_versions) || 1,
    extra_instructions: form.extra_instructions?.trim() || null,
  };
  if (modelConfigSelection.value != null) {
    payload.model_config_id = modelConfigSelection.value;
  }
  // Advanced overrides — only include if user touched them
  if (form.temperature != null && form.temperature !== "") {
    payload.temperature = Number(form.temperature);
  }
  if (form.max_tokens != null && form.max_tokens !== "" && form.max_tokens > 0) {
    payload.max_tokens = Number(form.max_tokens);
  }
  if (form.system_prompt_override?.trim()) {
    payload.system_prompt_override = form.system_prompt_override.trim();
  }
  return payload;
}

async function onGenerate() {
  if (!form.topic.trim()) {
    ElMessage.warning(t("copyGen.quickGen.topicRequired"));
    return;
  }
  if (!hasModel.value) {
    ElMessage.warning(t("copyGen.quickGen.noModelWarning"));
    return;
  }
  errorMsg.value = "";
  abortController = new AbortController();
  try {
    const payload = buildPayload();
    if (agentSelection.value) {
      await store.generateWithAgent(agentSelection.value, payload, {
        signal: abortController.signal,
      });
    } else {
      await store.generate(payload, {
        signal: abortController.signal,
      });
    }
    ElMessage.success(t("copyGen.quickGen.generateSuccess"));
  } catch (e) {
    const aborted =
      e?.name === "CanceledError" ||
      e?.code === "ERR_CANCELED" ||
      e?.message === "canceled";
    if (aborted) {
      ElMessage.info(t("copyGen.quickGen.canceled"));
    } else {
      errorMsg.value = e?.response?.data?.detail || e?.message || String(e);
      ElMessage.error(
        t("copyGen.common.errorMsg", { msg: errorMsg.value })
      );
    }
  } finally {
    abortController = null;
  }
}

function onCancel() {
  if (abortController) {
    try {
      abortController.abort();
    } catch {
      // ignore
    }
  }
}

function onSendTTS(version) {
  if (!version) return;
  sendTTSVersion.value = version;
  sendTTSVisible.value = true;
}

function onReuseHistory(item) {
  const p = item?.payload;
  if (!p) return;
  form.topic = p.topic || "";
  form.platform = p.platform || "";
  form.template = p.template || "";
  form.script_type = p.script_type || "single";
  form.target_words = p.target_words || 300;
  form.tolerance = p.tolerance || 50;
  form.num_versions = p.num_versions || 3;
  form.extra_instructions = p.extra_instructions || "";
  if (p.model_config_id != null) {
    modelConfigSelection.value = p.model_config_id;
  }
  if (item?.agent_id != null) {
    agentSelection.value = item.agent_id;
  }
  ElMessage.info(t("copyGen.history.reused"));
}

onBeforeUnmount(() => {
  // Abort any in-flight generation when leaving the page
  if (abortController) {
    try {
      abortController.abort();
    } catch {
      // ignore
    }
  }
});
</script>
