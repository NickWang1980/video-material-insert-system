<template>
  <div class="copy-gen-model-config-manager space-y-4">
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-lg font-semibold dark:text-gray-100">
          {{ t("copyGen.modelConfig.title") }}
        </h2>
        <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">
          {{ t("copyGen.modelConfig.subtitle") }}
        </p>
      </div>
      <el-button type="primary" @click="openDialog(null)">
        {{ t("copyGen.modelConfig.add") }}
      </el-button>
    </div>

    <el-card shadow="never" class="dark:!bg-gray-800 dark:!border-gray-700">
      <el-table
        :data="store.modelConfigs"
        :empty-text="t('copyGen.modelConfig.empty')"
        size="small"
        border
        v-loading="store.loading.models"
      >
        <el-table-column prop="name" :label="t('copyGen.modelConfig.name')" min-width="160" />
        <el-table-column
          prop="model_name"
          :label="t('copyGen.modelConfig.modelName')"
          min-width="160"
        />
        <el-table-column
          prop="base_url"
          :label="t('copyGen.modelConfig.baseUrl')"
          min-width="220"
          show-overflow-tooltip
        />
        <el-table-column :label="t('copyGen.modelConfig.apiKey')" width="100">
          <template #default="{ row }">
            <el-tag
              size="small"
              :type="row.has_api_key ? 'success' : 'info'"
              effect="plain"
            >
              {{
                row.has_api_key
                  ? t("copyGen.modelConfig.apiKeySet")
                  : t("copyGen.modelConfig.apiKeyNone")
              }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('copyGen.modelConfig.createdAt')" width="160">
          <template #default="{ row }">
            <span class="text-xs text-gray-500">{{ formatTime(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('copyGen.common.actions')" width="240" fixed="right">
          <template #default="{ row }">
            <el-button
              size="small"
              text
              :loading="testingId === row.id"
              @click="onTest(row)"
            >
              {{ t("copyGen.modelConfig.test") }}
            </el-button>
            <el-button size="small" text type="primary" @click="openDialog(row)">
              {{ t("copyGen.common.edit") }}
            </el-button>
            <el-popconfirm
              :title="t('copyGen.modelConfig.confirmDelete')"
              :confirm-button-text="t('copyGen.common.confirm')"
              :cancel-button-text="t('copyGen.common.cancel')"
              @confirm="onDelete(row)"
            >
              <template #reference>
                <el-button size="small" text type="danger">
                  {{ t("copyGen.common.delete") }}
                </el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Edit/Create dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="
        editingId
          ? t('copyGen.modelConfig.dialogEditTitle')
          : t('copyGen.modelConfig.dialogCreateTitle')
      "
      width="640"
      :close-on-click-modal="false"
    >
      <el-form label-position="top" :model="form">
        <el-form-item :label="t('copyGen.modelConfig.name')" required>
          <el-input
            v-model="form.name"
            :placeholder="t('copyGen.modelConfig.namePlaceholder')"
          />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item :label="t('copyGen.modelConfig.modelName')" required>
              <el-input
                v-model="form.model_name"
                :placeholder="t('copyGen.modelConfig.modelNamePlaceholder')"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="t('copyGen.modelConfig.baseUrl')" required>
              <el-input
                v-model="form.base_url"
                :placeholder="t('copyGen.modelConfig.baseUrlPlaceholder')"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item :label="t('copyGen.modelConfig.apiKey')">
          <el-input
            v-model="form.api_key"
            :placeholder="apiKeyPlaceholder"
            type="password"
            show-password
            autocomplete="off"
          />
          <div
            v-if="editingId && editingRow?.has_api_key && !form.api_key"
            class="text-xs text-gray-400 mt-1"
          >
            {{ t("copyGen.modelConfig.apiKeyKeepHint") }}
          </div>
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item :label="t('copyGen.modelConfig.temperature')">
              <div class="flex items-center gap-3">
                <el-slider
                  v-model="form.temperature"
                  :min="0"
                  :max="2"
                  :step="0.1"
                  class="flex-1"
                />
                <span class="text-xs font-mono w-10 text-right">
                  {{ form.temperature.toFixed(1) }}
                </span>
              </div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="t('copyGen.modelConfig.maxTokens')">
              <el-input-number
                v-model="form.max_tokens"
                :min="128"
                :max="32000"
                :step="256"
                class="!w-full"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item :label="t('copyGen.modelConfig.systemPrompt')">
          <el-input
            v-model="form.system_prompt"
            type="textarea"
            :rows="4"
            :placeholder="t('copyGen.modelConfig.systemPromptPlaceholder')"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">
          {{ t("copyGen.common.cancel") }}
        </el-button>
        <el-button type="primary" :loading="saving" @click="onSave">
          {{ t("copyGen.common.save") }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from "vue";
import { ElMessage } from "element-plus";
import { useI18n } from "vue-i18n";
import { useCopyGenStore } from "../../store/modules/copyGen";

const { t } = useI18n();
const store = useCopyGenStore();

const dialogVisible = ref(false);
const saving = ref(false);
const editingId = ref(null);
const editingRow = ref(null);
const testingId = ref(null);

const form = reactive({
  name: "",
  model_name: "",
  base_url: "https://api.openai.com/v1",
  api_key: "",
  temperature: 0.8,
  max_tokens: 4096,
  system_prompt: "",
});

const apiKeyPlaceholder = computed(() => {
  if (editingId.value && editingRow.value?.has_api_key) {
    return t("copyGen.modelConfig.apiKeyUnchanged");
  }
  return t("copyGen.modelConfig.apiKeyPlaceholder");
});

function resetForm() {
  form.name = "";
  form.model_name = "";
  form.base_url = "https://api.openai.com/v1";
  form.api_key = "";
  form.temperature = 0.8;
  form.max_tokens = 4096;
  form.system_prompt = "";
}

function openDialog(row) {
  if (row) {
    editingId.value = row.id;
    editingRow.value = row;
    form.name = row.name || "";
    form.model_name = row.model_name || "";
    form.base_url = row.base_url || "https://api.openai.com/v1";
    form.api_key = "";
    form.temperature =
      typeof row.temperature === "number" ? row.temperature : 0.8;
    form.max_tokens =
      typeof row.max_tokens === "number" ? row.max_tokens : 4096;
    form.system_prompt = row.system_prompt || "";
  } else {
    editingId.value = null;
    editingRow.value = null;
    resetForm();
  }
  dialogVisible.value = true;
}

async function onSave() {
  if (!form.name.trim() || !form.model_name.trim() || !form.base_url.trim()) {
    ElMessage.warning(t("copyGen.modelConfig.validationFail"));
    return;
  }
  saving.value = true;
  try {
    const payload = {
      name: form.name.trim(),
      model_name: form.model_name.trim(),
      base_url: form.base_url.trim(),
      temperature: Number(form.temperature),
      max_tokens: Number(form.max_tokens) || 4096,
      system_prompt: form.system_prompt || null,
    };
    // 仅当用户输入了新的 api_key 才发送；编辑模式下不发送 -> 后端保留原值
    if (form.api_key) {
      payload.api_key = form.api_key;
    }
    if (editingId.value) {
      await store.updateModelConfig(editingId.value, payload);
      ElMessage.success(t("copyGen.modelConfig.updateSuccess"));
    } else {
      if (!form.api_key) {
        // 新建必须有 api_key（除非后端默认允许空，安全起见提示）
        ElMessage.warning(t("copyGen.modelConfig.apiKeyRequired"));
        saving.value = false;
        return;
      }
      await store.createModelConfig(payload);
      ElMessage.success(t("copyGen.modelConfig.createSuccess"));
    }
    dialogVisible.value = false;
  } catch (e) {
    ElMessage.error(
      t("copyGen.common.errorMsg", { msg: e?.message || String(e) })
    );
  } finally {
    saving.value = false;
  }
}

async function onDelete(row) {
  if (!row?.id) return;
  try {
    await store.deleteModelConfig(row.id);
    ElMessage.success(t("copyGen.modelConfig.deleteSuccess"));
  } catch (e) {
    ElMessage.error(
      t("copyGen.common.errorMsg", { msg: e?.message || String(e) })
    );
  }
}

async function onTest(row) {
  if (!row?.id) return;
  testingId.value = row.id;
  try {
    const result = await store.testModelConfig(row.id);
    if (result?.success || result?.ok) {
      ElMessage.success(
        t("copyGen.modelConfig.testSuccess", {
          model: result?.model || row.model_name,
        })
      );
    } else {
      ElMessage.error(
        t("copyGen.modelConfig.testFailed", {
          msg: result?.error || result?.message || "unknown",
        })
      );
    }
  } catch (e) {
    ElMessage.error(
      t("copyGen.modelConfig.testFailed", {
        msg: e?.message || String(e),
      })
    );
  } finally {
    testingId.value = null;
  }
}

function formatTime(ts) {
  if (!ts) return "";
  try {
    const d = typeof ts === "string" ? new Date(ts) : new Date(Number(ts));
    return d.toLocaleString();
  } catch {
    return String(ts);
  }
}
</script>
