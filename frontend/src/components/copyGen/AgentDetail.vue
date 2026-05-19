<template>
  <div class="copy-gen-agent-detail space-y-4">
    <!-- Basic info form -->
    <el-card shadow="never" class="dark:!bg-gray-800 dark:!border-gray-700">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="font-semibold dark:text-gray-100">
            {{
              isCreate
                ? t("copyGen.agent.createTitle")
                : t("copyGen.agent.editTitle")
            }}
          </span>
          <el-tag v-if="!isCreate && form.is_active" type="success" size="small">
            {{ t("copyGen.agent.active") }}
          </el-tag>
          <el-tag v-else-if="!isCreate" type="info" size="small">
            {{ t("copyGen.agent.inactive") }}
          </el-tag>
        </div>
      </template>

      <el-form label-position="top" :model="form">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item :label="t('copyGen.agent.name')" required>
              <el-input
                v-model="form.name"
                :placeholder="t('copyGen.agent.namePlaceholder')"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="t('copyGen.agent.platform')">
              <el-select
                v-model="form.platform"
                :placeholder="t('copyGen.agent.platformPlaceholder')"
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
        </el-row>
        <el-form-item :label="t('copyGen.agent.description')">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="2"
            :placeholder="t('copyGen.agent.descriptionPlaceholder')"
          />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item :label="t('copyGen.agent.industry')">
              <el-input
                v-model="form.industry"
                :placeholder="t('copyGen.agent.industryPlaceholder')"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="t('copyGen.agent.defaultTemplate')">
              <el-select
                v-model="form.default_template"
                :placeholder="t('copyGen.agent.defaultTemplatePlaceholder')"
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
        </el-row>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item :label="t('copyGen.agent.defaultTargetWords')">
              <el-input-number
                v-model="form.default_target_words"
                :min="50"
                :max="2000"
                :step="50"
                class="!w-full"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item :label="t('copyGen.agent.defaultTolerance')">
              <el-input-number
                v-model="form.default_tolerance"
                :min="0"
                :max="500"
                :step="10"
                class="!w-full"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item :label="t('copyGen.agent.defaultScriptType')">
              <el-radio-group v-model="form.default_script_type">
                <el-radio value="single">
                  {{ t("copyGen.agent.scriptSingle") }}
                </el-radio>
                <el-radio value="ab_role">
                  {{ t("copyGen.agent.scriptAB") }}
                </el-radio>
              </el-radio-group>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item :label="t('copyGen.agent.modelConfig')">
              <el-select
                v-model="form.model_config_id"
                :placeholder="t('copyGen.agent.modelConfigPlaceholder')"
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
          <el-col :span="12">
            <el-form-item :label="t('copyGen.agent.isActive')">
              <el-switch v-model="form.is_active" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <div class="flex items-center justify-end gap-2 pt-2 border-t border-gray-100 dark:border-gray-700">
        <el-popconfirm
          v-if="!isCreate"
          :title="t('copyGen.agent.confirmDelete')"
          :confirm-button-text="t('copyGen.common.confirm')"
          :cancel-button-text="t('copyGen.common.cancel')"
          @confirm="onDelete"
        >
          <template #reference>
            <el-button type="danger" plain>
              {{ t("copyGen.common.delete") }}
            </el-button>
          </template>
        </el-popconfirm>
        <el-button type="primary" :loading="saving" @click="onSave">
          {{
            isCreate
              ? t("copyGen.common.create")
              : t("copyGen.common.save")
          }}
        </el-button>
      </div>
    </el-card>

    <!-- Rules + Knowledge tabs (only when saved) -->
    <el-card
      v-if="!isCreate && agentId"
      shadow="never"
      class="dark:!bg-gray-800 dark:!border-gray-700"
    >
      <el-tabs v-model="activeTab">
        <el-tab-pane :label="t('copyGen.rule.tabLabel')" name="rules">
          <RuleEditor :agent-id="agentId" :rules="rules" />
        </el-tab-pane>
        <el-tab-pane :label="t('copyGen.knowledge.tabLabel')" name="knowledge">
          <KnowledgeEditor :agent-id="agentId" :knowledge="knowledge" />
        </el-tab-pane>
      </el-tabs>
    </el-card>
    <el-alert
      v-else-if="isCreate"
      :title="t('copyGen.agent.saveFirstHint')"
      type="info"
      :closable="false"
      show-icon
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch } from "vue";
import { ElMessage } from "element-plus";
import { useI18n } from "vue-i18n";
import { useCopyGenStore } from "../../store/modules/copyGen";
import RuleEditor from "./RuleEditor.vue";
import KnowledgeEditor from "./KnowledgeEditor.vue";

const props = defineProps({
  agent: { type: Object, default: null }, // null = create mode
  isCreate: { type: Boolean, default: false },
});
const emit = defineEmits(["saved", "deleted"]);
const { t } = useI18n();
const store = useCopyGenStore();

const activeTab = ref("rules");
const saving = ref(false);

const form = reactive({
  name: "",
  description: "",
  platform: "",
  industry: "",
  default_template: "",
  default_target_words: 300,
  default_tolerance: 50,
  default_script_type: "single",
  model_config_id: null,
  is_active: true,
});

const agentId = computed(() =>
  props.agent?.id != null ? props.agent.id : null
);

// Prefer the freshly fetched detail (which has rules / knowledge) over the summary list prop
const detail = computed(() => {
  if (
    store.currentAgentDetail &&
    store.currentAgentDetail.id === agentId.value
  ) {
    return store.currentAgentDetail;
  }
  return props.agent || null;
});

const rules = computed(() =>
  Array.isArray(detail.value?.rules) ? detail.value.rules : []
);
const knowledge = computed(() =>
  Array.isArray(detail.value?.knowledge) ? detail.value.knowledge : []
);

const platforms = computed(() => store.enums.platforms || []);
const templates = computed(() => store.enums.templates || []);

function syncFromAgent(a) {
  if (!a) {
    form.name = "";
    form.description = "";
    form.platform = "";
    form.industry = "";
    form.default_template = "";
    form.default_target_words = 300;
    form.default_tolerance = 50;
    form.default_script_type = "single";
    form.model_config_id = null;
    form.is_active = true;
    return;
  }
  form.name = a.name || "";
  form.description = a.description || "";
  form.platform = a.platform || "";
  form.industry = a.industry || "";
  form.default_template = a.default_template || "";
  form.default_target_words =
    typeof a.default_target_words === "number" ? a.default_target_words : 300;
  form.default_tolerance =
    typeof a.default_tolerance === "number" ? a.default_tolerance : 50;
  form.default_script_type = a.default_script_type || "single";
  form.model_config_id = a.model_config_id ?? null;
  form.is_active = a.is_active !== false;
}

watch(
  () => props.agent,
  (a) => syncFromAgent(a),
  { immediate: true }
);

// Auto-load detail (rules + knowledge) when agent changes
watch(
  agentId,
  async (id) => {
    if (id == null) return;
    try {
      await store.fetchAgentDetail(id);
    } catch (e) {
      // eslint-disable-next-line no-console
      console.warn("[AgentDetail] fetchAgentDetail failed", e);
    }
  },
  { immediate: true }
);

async function onSave() {
  if (!form.name.trim()) {
    ElMessage.warning(t("copyGen.agent.nameRequired"));
    return;
  }
  saving.value = true;
  try {
    const payload = {
      name: form.name.trim(),
      description: form.description?.trim() || null,
      platform: form.platform || null,
      industry: form.industry?.trim() || null,
      default_template: form.default_template || null,
      default_target_words: Number(form.default_target_words) || 300,
      default_tolerance: Number(form.default_tolerance) || 50,
      default_script_type: form.default_script_type || "single",
      model_config_id: form.model_config_id ?? null,
      is_active: !!form.is_active,
    };
    let saved;
    if (props.isCreate || !agentId.value) {
      saved = await store.createAgent(payload);
      ElMessage.success(t("copyGen.agent.createSuccess"));
    } else {
      saved = await store.updateAgent(agentId.value, payload);
      ElMessage.success(t("copyGen.agent.updateSuccess"));
    }
    emit("saved", saved);
  } catch (e) {
    ElMessage.error(
      t("copyGen.common.errorMsg", { msg: e?.message || String(e) })
    );
  } finally {
    saving.value = false;
  }
}

async function onDelete() {
  if (!agentId.value) return;
  try {
    await store.deleteAgent(agentId.value);
    ElMessage.success(t("copyGen.agent.deleteSuccess"));
    emit("deleted", agentId.value);
  } catch (e) {
    ElMessage.error(
      t("copyGen.common.errorMsg", { msg: e?.message || String(e) })
    );
  }
}
</script>
