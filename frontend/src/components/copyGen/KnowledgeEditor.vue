<template>
  <div class="copy-gen-knowledge-editor space-y-3">
    <div class="flex items-center justify-between">
      <span class="text-sm font-semibold dark:text-gray-100">
        {{ t("copyGen.knowledge.title") }}
        <span class="text-xs text-gray-500 dark:text-gray-400 ml-2">
          {{ t("copyGen.knowledge.count", { count: knowledge.length }) }}
        </span>
      </span>
      <el-button
        type="primary"
        size="small"
        :disabled="!agentId"
        @click="openDialog(null)"
      >
        {{ t("copyGen.knowledge.add") }}
      </el-button>
    </div>

    <el-table
      :data="knowledge"
      :empty-text="t('copyGen.knowledge.empty')"
      size="small"
      border
      v-loading="store.loading.knowledge"
    >
      <el-table-column prop="category" :label="t('copyGen.knowledge.category')" width="140" />
      <el-table-column prop="title" :label="t('copyGen.knowledge.titleField')" width="180" />
      <el-table-column :label="t('copyGen.knowledge.content')" min-width="240">
        <template #default="{ row }">
          <div class="whitespace-pre-wrap text-sm">{{ row.content }}</div>
        </template>
      </el-table-column>
      <el-table-column :label="t('copyGen.knowledge.status')" width="120">
        <template #default="{ row }">
          <el-tag size="small" :type="statusTagType(row.status)" effect="plain">
            {{ statusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column :label="t('copyGen.common.actions')" width="160" fixed="right">
        <template #default="{ row }">
          <el-button size="small" text type="primary" @click="openDialog(row)">
            {{ t("copyGen.common.edit") }}
          </el-button>
          <el-popconfirm
            :title="t('copyGen.knowledge.confirmDelete')"
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

    <el-dialog
      v-model="dialogVisible"
      :title="
        editingId
          ? t('copyGen.knowledge.dialogEditTitle')
          : t('copyGen.knowledge.dialogCreateTitle')
      "
      width="560"
      :close-on-click-modal="false"
    >
      <el-form label-position="top" :model="form">
        <el-form-item :label="t('copyGen.knowledge.category')" required>
          <el-select
            v-model="form.category"
            :placeholder="t('copyGen.knowledge.categoryPlaceholder')"
            class="!w-full"
            filterable
            allow-create
            default-first-option
          >
            <el-option
              v-for="c in knowledgeCategories"
              :key="c.code || c"
              :label="c.name || c.code || c"
              :value="c.code || c"
            />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('copyGen.knowledge.titleField')" required>
          <el-input
            v-model="form.title"
            :placeholder="t('copyGen.knowledge.titlePlaceholder')"
          />
        </el-form-item>
        <el-form-item :label="t('copyGen.knowledge.content')" required>
          <el-input
            v-model="form.content"
            type="textarea"
            :rows="5"
            :placeholder="t('copyGen.knowledge.contentPlaceholder')"
          />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item :label="t('copyGen.knowledge.status')">
              <el-select v-model="form.status" class="!w-full">
                <el-option
                  :label="t('copyGen.knowledge.statusActive')"
                  value="active"
                />
                <el-option
                  :label="t('copyGen.knowledge.statusOutdated')"
                  value="outdated"
                />
                <el-option
                  :label="t('copyGen.knowledge.statusConflict')"
                  value="conflict"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="t('copyGen.knowledge.statusNote')">
              <el-input
                v-model="form.status_note"
                :placeholder="t('copyGen.knowledge.statusNotePlaceholder')"
              />
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
  knowledge: { type: Array, default: () => [] },
});

const { t } = useI18n();
const store = useCopyGenStore();

const dialogVisible = ref(false);
const saving = ref(false);
const editingId = ref(null);

const form = reactive({
  category: "",
  title: "",
  content: "",
  status: "active",
  status_note: "",
});

const knowledgeCategories = computed(() => store.enums.knowledgeCategories || []);

function resetForm() {
  form.category = "";
  form.title = "";
  form.content = "";
  form.status = "active";
  form.status_note = "";
}

function openDialog(row) {
  if (row) {
    editingId.value = row.id;
    form.category = row.category || "";
    form.title = row.title || "";
    form.content = row.content || "";
    form.status = row.status || "active";
    form.status_note = row.status_note || "";
  } else {
    editingId.value = null;
    resetForm();
  }
  dialogVisible.value = true;
}

async function onSave() {
  if (!props.agentId) {
    ElMessage.warning(t("copyGen.knowledge.noAgent"));
    return;
  }
  if (
    !form.category.trim() ||
    !form.title.trim() ||
    !form.content.trim()
  ) {
    ElMessage.warning(t("copyGen.knowledge.validationFail"));
    return;
  }
  saving.value = true;
  try {
    const payload = {
      category: form.category.trim(),
      title: form.title.trim(),
      content: form.content.trim(),
      status: form.status || "active",
      status_note: form.status_note?.trim() || null,
    };
    if (editingId.value) {
      await store.updateKnowledge(props.agentId, editingId.value, payload);
      ElMessage.success(t("copyGen.knowledge.updateSuccess"));
    } else {
      await store.createKnowledge(props.agentId, payload);
      ElMessage.success(t("copyGen.knowledge.createSuccess"));
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
    await store.deleteKnowledge(props.agentId, row.id);
    ElMessage.success(t("copyGen.knowledge.deleteSuccess"));
  } catch (e) {
    ElMessage.error(
      t("copyGen.common.errorMsg", { msg: e?.message || String(e) })
    );
  }
}

function statusLabel(s) {
  if (s === "outdated") return t("copyGen.knowledge.statusOutdated");
  if (s === "conflict") return t("copyGen.knowledge.statusConflict");
  return t("copyGen.knowledge.statusActive");
}

function statusTagType(s) {
  if (s === "outdated") return "info";
  if (s === "conflict") return "danger";
  return "success";
}
</script>
