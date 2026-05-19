<template>
  <div class="copy-gen-rule-editor space-y-3">
    <div class="flex items-center justify-between">
      <span class="text-sm font-semibold dark:text-gray-100">
        {{ t("copyGen.rule.title") }}
        <span class="text-xs text-gray-500 dark:text-gray-400 ml-2">
          {{ t("copyGen.rule.count", { count: rules.length }) }}
        </span>
      </span>
      <el-button
        type="primary"
        size="small"
        :disabled="!agentId"
        @click="openDialog(null)"
      >
        {{ t("copyGen.rule.add") }}
      </el-button>
    </div>

    <el-table
      :data="rules"
      :empty-text="t('copyGen.rule.empty')"
      size="small"
      border
      v-loading="store.loading.rules"
    >
      <el-table-column prop="category" :label="t('copyGen.rule.category')" width="140" />
      <el-table-column :label="t('copyGen.rule.content')" min-width="240">
        <template #default="{ row }">
          <div class="whitespace-pre-wrap text-sm">{{ row.content }}</div>
        </template>
      </el-table-column>
      <el-table-column :label="t('copyGen.rule.ruleType')" width="100">
        <template #default="{ row }">
          <el-tag
            size="small"
            :type="row.rule_type === 'negative' ? 'danger' : 'success'"
            effect="plain"
          >
            {{
              row.rule_type === "negative"
                ? t("copyGen.rule.typeNegative")
                : t("copyGen.rule.typePositive")
            }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="priority" :label="t('copyGen.rule.priority')" width="80" />
      <el-table-column prop="source" :label="t('copyGen.rule.source')" width="120" />
      <el-table-column :label="t('copyGen.common.actions')" width="160" fixed="right">
        <template #default="{ row }">
          <el-button size="small" text type="primary" @click="openDialog(row)">
            {{ t("copyGen.common.edit") }}
          </el-button>
          <el-popconfirm
            :title="t('copyGen.rule.confirmDelete')"
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

    <!-- Edit/Create dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="
        editingId
          ? t('copyGen.rule.dialogEditTitle')
          : t('copyGen.rule.dialogCreateTitle')
      "
      width="560"
      :close-on-click-modal="false"
    >
      <el-form label-position="top" :model="form">
        <el-form-item :label="t('copyGen.rule.category')" required>
          <el-select
            v-model="form.category"
            :placeholder="t('copyGen.rule.categoryPlaceholder')"
            class="!w-full"
            filterable
            allow-create
            default-first-option
          >
            <el-option
              v-for="c in ruleCategories"
              :key="c.code || c"
              :label="c.name || c.code || c"
              :value="c.code || c"
            />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('copyGen.rule.content')" required>
          <el-input
            v-model="form.content"
            type="textarea"
            :rows="4"
            :placeholder="t('copyGen.rule.contentPlaceholder')"
          />
        </el-form-item>
        <el-form-item :label="t('copyGen.rule.originalContent')">
          <el-input
            v-model="form.original_content"
            type="textarea"
            :rows="2"
            :placeholder="t('copyGen.rule.originalContentPlaceholder')"
          />
        </el-form-item>
        <el-form-item :label="t('copyGen.rule.ruleType')">
          <el-radio-group v-model="form.rule_type">
            <el-radio value="positive">
              {{ t("copyGen.rule.typePositive") }}
            </el-radio>
            <el-radio value="negative">
              {{ t("copyGen.rule.typeNegative") }}
            </el-radio>
          </el-radio-group>
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item :label="t('copyGen.rule.priority')">
              <el-input-number
                v-model="form.priority"
                :min="0"
                :max="100"
                class="!w-full"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="t('copyGen.rule.source')">
              <el-select
                v-model="form.source"
                :placeholder="t('copyGen.rule.sourcePlaceholder')"
                class="!w-full"
                clearable
              >
                <el-option label="manual" value="manual" />
                <el-option label="document" value="document" />
                <el-option label="example" value="example" />
                <el-option label="merged" value="merged" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
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
import { computed, ref, reactive } from "vue";
import { ElMessage } from "element-plus";
import { useI18n } from "vue-i18n";
import { useCopyGenStore } from "../../store/modules/copyGen";

const props = defineProps({
  agentId: { type: Number, default: null },
  rules: { type: Array, default: () => [] },
});

const { t } = useI18n();
const store = useCopyGenStore();

const dialogVisible = ref(false);
const saving = ref(false);
const editingId = ref(null);

const form = reactive({
  category: "",
  content: "",
  original_content: "",
  rule_type: "positive",
  priority: 50,
  source: "manual",
});

const ruleCategories = computed(() => store.enums.ruleCategories || []);

function resetForm() {
  form.category = "";
  form.content = "";
  form.original_content = "";
  form.rule_type = "positive";
  form.priority = 50;
  form.source = "manual";
}

function openDialog(row) {
  if (row) {
    editingId.value = row.id;
    form.category = row.category || "";
    form.content = row.content || "";
    form.original_content = row.original_content || "";
    form.rule_type = row.rule_type || "positive";
    form.priority = typeof row.priority === "number" ? row.priority : 50;
    form.source = row.source || "manual";
  } else {
    editingId.value = null;
    resetForm();
  }
  dialogVisible.value = true;
}

async function onSave() {
  if (!props.agentId) {
    ElMessage.warning(t("copyGen.rule.noAgent"));
    return;
  }
  if (!form.category.trim() || !form.content.trim()) {
    ElMessage.warning(t("copyGen.rule.validationFail"));
    return;
  }
  saving.value = true;
  try {
    const payload = {
      category: form.category.trim(),
      content: form.content.trim(),
      original_content: form.original_content?.trim() || null,
      rule_type: form.rule_type,
      priority: Number(form.priority) || 0,
      source: form.source || "manual",
    };
    if (editingId.value) {
      await store.updateRule(props.agentId, editingId.value, payload);
      ElMessage.success(t("copyGen.rule.updateSuccess"));
    } else {
      await store.createRule(props.agentId, payload);
      ElMessage.success(t("copyGen.rule.createSuccess"));
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
  if (!props.agentId || !row?.id) return;
  try {
    await store.deleteRule(props.agentId, row.id);
    ElMessage.success(t("copyGen.rule.deleteSuccess"));
  } catch (e) {
    ElMessage.error(
      t("copyGen.common.errorMsg", { msg: e?.message || String(e) })
    );
  }
}
</script>
