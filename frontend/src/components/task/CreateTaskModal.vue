<template>
  <el-dialog v-model="open" title="新建剪辑任务" width="760px">
    <div class="space-y-4">
      <div>
        <div class="text-sm font-medium mb-2">任务名称</div>
        <el-input v-model="form.task_name" placeholder="请输入任务名称" />
      </div>

      <div>
        <div class="text-sm font-medium mb-2">选择源视频条目</div>
        <el-select
          v-model="form.source_entry_id"
          class="w-full"
          filterable
          placeholder="请选择源视频条目（SRT可选）"
        >
          <el-option
            v-for="entry in sourceEntries"
            :key="entry.id"
            :label="`${entry.name}（${entry.video_aspect_ratio} · ${entry.video_width}×${entry.video_height}）`"
            :value="entry.id"
          />
        </el-select>

        <div class="mt-2 grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <div class="text-xs text-gray-500 mb-1">字幕来源</div>
            <el-select v-model="form.subtitle_source" class="w-full">
              <el-option label="用户上传SRT" value="uploaded" :disabled="!uploadedReady" />
              <el-option label="ASR SRT" value="asr" :disabled="!asrReady" />
            </el-select>
          </div>
          <div class="text-xs text-gray-500 flex items-end pb-2">
            <span v-if="!form.source_entry_id">请先选择源视频条目后再切换字幕来源。</span>
            <span v-else-if="uploadedReady && asrReady">当前条目上传SRT与ASR SRT都可用。</span>
            <span v-else-if="uploadedReady">当前条目仅有上传SRT可用。</span>
            <span v-else-if="asrReady">当前条目 ASR SRT 已可用，可直接创建任务。</span>
            <span v-else>当前条目暂无可用字幕，请等待ASR完成。</span>
          </div>
        </div>

        <div class="mt-3">
          <el-checkbox v-model="form.add_subtitle_to_video">添加字幕SRT到视频</el-checkbox>
        </div>
      </div>

      <div>
        <div class="text-sm font-medium mb-2">选择模板（可多选）</div>
        <el-select
          v-model="form.config_ids"
          class="w-full"
          multiple
          collapse-tags
          collapse-tags-tooltip
          placeholder="请选择一个或多个模板"
          :loading="checkingConflicts"
          @change="checkConflicts"
        >
          <el-option
            v-for="template in templates"
            :key="template.id"
            :label="template.template_name"
            :value="template.id"
          />
        </el-select>
        <div class="mt-2 flex items-center justify-between gap-2">
          <div class="text-xs text-gray-500">
            任务创建仅支持多模板合并；如多个模板存在同一关键词，将阻止提交。
          </div>
          <el-button
            size="small"
            plain
            :disabled="conflictGroups.length === 0"
            @click="layerDialogVisible = true"
          >
            冲突层级设置
          </el-button>
        </div>
      </div>

      <el-alert
        v-if="conflicts.length > 0"
        type="error"
        show-icon
        :closable="false"
        title="模板关键词冲突，请调整模板组合"
      >
        <div class="text-xs mt-1 space-y-1">
          <div v-for="item in conflicts" :key="item.keyword">
            关键词「{{ item.keyword }}」：{{ item.templateNames.join(" / ") }}
          </div>
        </div>
      </el-alert>

      <el-alert
        v-if="keywordCollisionWarnings.length > 0"
        type="warning"
        show-icon
        :closable="false"
        title="检测到关键词冲突，请点击“冲突层级设置”"
      >
        <div class="text-xs mt-1">
          已检测到 {{ conflictGroups.length }} 组冲突，请点击“冲突层级设置”按时间分组拖拽调整优先顺序。
        </div>
      </el-alert>
    </div>

    <template #footer>
      <div class="flex items-center justify-end gap-2">
        <el-button @click="open = false">取消</el-button>
        <el-button type="primary" :loading="submitting" :disabled="!canSubmit" @click="submit">
          提交
        </el-button>
      </div>
    </template>
  </el-dialog>

  <el-dialog
    v-model="layerDialogVisible"
    title="模板层级设置"
    width="760px"
    destroy-on-close
  >
    <div class="space-y-4">
      <div class="text-xs text-gray-500">
        仅展示关键词冲突相关行；按冲突时间段分组，可在组内拖拽上下调整优先顺序（上方优先级更高）。
      </div>
      <div v-if="conflictGroups.length === 0" class="text-sm text-gray-500">当前无冲突分组。</div>
      <div
        v-for="group in conflictGroups"
        :key="group.id"
        class="rounded-lg border border-gray-200 bg-gray-50 p-3 space-y-2"
      >
        <div class="text-sm font-medium">
          冲突组 #{{ group.subtitle_index }}（{{ group.start }} - {{ group.end }}）
        </div>
        <div class="text-xs text-gray-500 truncate">{{ group.text }}</div>
        <div class="space-y-2">
          <div
            v-for="entry in group.entries"
            :key="entry.keyword"
            class="rounded border border-gray-200 bg-white px-3 py-2 cursor-move"
            draggable="true"
            @dragstart="onDragStart(group.id, entry.keyword)"
            @dragover.prevent
            @drop="onDrop(group.id, entry.keyword)"
          >
            <div class="flex items-center justify-between gap-2">
              <div class="text-sm font-medium">{{ entry.keyword }}</div>
              <div class="text-xs text-gray-500">{{ entry.template_name }}</div>
            </div>
            <div class="text-xs text-gray-500 mt-1 truncate">
              素材：{{ entry.material_file_name || "-" }} / {{ entry.material_type || "-" }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { useConfigStore } from "../../store/modules/config";
import { useTaskStore } from "../../store/modules/task";

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  templates: { type: Array, default: () => [] },
  sourceEntries: { type: Array, default: () => [] },
});
const emit = defineEmits(["update:modelValue", "submit"]);

const configStore = useConfigStore();
const taskStore = useTaskStore();

const open = computed({
  get: () => props.modelValue,
  set: (value) => emit("update:modelValue", value),
});

const form = reactive({
  task_name: "",
  source_entry_id: null,
  subtitle_source: "uploaded",
  add_subtitle_to_video: false,
  config_ids: [],
});

const layerDialogVisible = ref(false);
const submitting = ref(false);
const conflicts = ref([]);
const checkingConflicts = ref(false);
const conflictCheckToken = ref(0);
const keywordCollisionWarnings = ref([]);
const checkingKeywordCollision = ref(false);
const keywordCollisionToken = ref(0);
const templateDetailsById = ref({});
const groupKeywordOrder = reactive({});
const dragState = reactive({ groupId: "", keyword: "" });

const selectedSourceEntry = computed(() =>
  props.sourceEntries.find((entry) => entry.id === form.source_entry_id)
);

const uploadedReady = computed(() => {
  const entry = selectedSourceEntry.value;
  if (!entry) return false;
  if (typeof entry.has_uploaded_srt === "boolean") {
    return entry.has_uploaded_srt;
  }
  return Number.isFinite(Number(entry.subtitle_line_count_user)) || !!entry.subtitle_path;
});

const asrReady = computed(() => {
  const entry = selectedSourceEntry.value;
  if (!entry) return false;
  if (typeof entry.has_asr_srt === "boolean") {
    return entry.has_asr_srt;
  }
  return !!entry.asr_srt_path;
});

const keywordRuleMap = computed(() => {
  const result = new Map();
  form.config_ids.forEach((templateId) => {
    const detail = templateDetailsById.value[templateId];
    if (!detail) return;
    const rules = Array.isArray(detail.config_content) ? detail.config_content : [];
    rules.forEach((rule) => {
        const keyword = String(rule?.["关键词"] || rule?.["关键字"] || "").trim();
      if (!keyword) return;
      if (result.has(keyword)) return;
      result.set(keyword, {
        keyword,
        template_id: detail.id,
        template_name: detail.template_name,
        material_file_name: String(rule?.["素材文件名"] || ""),
        material_type: String(rule?.["素材类型"] || ""),
      });
    });
  });
  return result;
});

const conflictGroups = computed(() => {
  return keywordCollisionWarnings.value.map((warning) => {
    const id = `${warning.subtitle_index}-${warning.start}-${warning.end}`;
    const defaultOrder = [warning.winner_keyword, ...(warning.suppressed_keywords || [])].filter(Boolean);
    const order = Array.isArray(groupKeywordOrder[id]) && groupKeywordOrder[id].length
      ? [...groupKeywordOrder[id]]
      : defaultOrder;
    const entries = order
      .map((keyword) => keywordRuleMap.value.get(keyword))
      .filter(Boolean);
    return {
      id,
      subtitle_index: warning.subtitle_index,
      start: warning.start,
      end: warning.end,
      text: warning.text,
      entries,
    };
  });
});

const collisionPriorityPayload = computed(() => {
  const payload = {};
  conflictGroups.value.forEach((group) => {
    const orderedKeywords = group.entries.map((entry) => entry.keyword).filter(Boolean);
    if (orderedKeywords.length > 1) {
      payload[group.subtitle_index] = orderedKeywords;
    }
  });
  return payload;
});

const canSubmit = computed(
  () =>
    !!form.task_name &&
    !!form.source_entry_id &&
    (uploadedReady.value || asrReady.value) &&
    form.config_ids.length > 0 &&
    conflicts.value.length === 0 &&
    !checkingConflicts.value &&
    !checkingKeywordCollision.value
);

function rebuildGroupOrders() {
  const nextIds = new Set();
  keywordCollisionWarnings.value.forEach((warning) => {
    const id = `${warning.subtitle_index}-${warning.start}-${warning.end}`;
    nextIds.add(id);
    const baseOrder = [warning.winner_keyword, ...(warning.suppressed_keywords || [])].filter(Boolean);
    const current = groupKeywordOrder[id];
    if (!Array.isArray(current) || current.length === 0) {
      groupKeywordOrder[id] = baseOrder;
      return;
    }
    const filtered = current.filter((keyword) => baseOrder.includes(keyword));
    baseOrder.forEach((keyword) => {
      if (!filtered.includes(keyword)) filtered.push(keyword);
    });
    groupKeywordOrder[id] = filtered;
  });
  Object.keys(groupKeywordOrder).forEach((id) => {
    if (!nextIds.has(id)) {
      delete groupKeywordOrder[id];
    }
  });
}

function onDragStart(groupId, keyword) {
  dragState.groupId = groupId;
  dragState.keyword = keyword;
}

function onDrop(groupId, targetKeyword) {
  if (dragState.groupId !== groupId || !dragState.keyword) return;
  const order = Array.isArray(groupKeywordOrder[groupId]) ? [...groupKeywordOrder[groupId]] : [];
  const from = order.indexOf(dragState.keyword);
  const to = order.indexOf(targetKeyword);
  if (from < 0 || to < 0 || from === to) return;
  const [item] = order.splice(from, 1);
  order.splice(to, 0, item);
  groupKeywordOrder[groupId] = order;
  dragState.groupId = "";
  dragState.keyword = "";
}

function resetForm() {
  form.task_name = "";
  form.source_entry_id = null;
  form.subtitle_source = "uploaded";
  form.add_subtitle_to_video = false;
  form.config_ids = [];
  conflicts.value = [];
  checkingConflicts.value = false;
  keywordCollisionWarnings.value = [];
  checkingKeywordCollision.value = false;
  layerDialogVisible.value = false;
  templateDetailsById.value = {};
  Object.keys(groupKeywordOrder).forEach((id) => delete groupKeywordOrder[id]);
}

async function checkConflicts() {
  const ids = [...form.config_ids];
  conflicts.value = [];
  if (ids.length === 0) {
    keywordCollisionWarnings.value = [];
    return;
  }

  const token = Date.now();
  conflictCheckToken.value = token;
  checkingConflicts.value = true;
  try {
    const templates = await Promise.all(ids.map((id) => configStore.getTemplate(id)));
    if (conflictCheckToken.value !== token) return;
    const map = {};
    templates.forEach((item) => {
      map[item.id] = item;
    });
    templateDetailsById.value = {
      ...templateDetailsById.value,
      ...map,
    };

    const keywordMap = new Map();
    const conflictMap = new Map();

    templates.forEach((template) => {
      const templateName = template.template_name;
      const rules = Array.isArray(template.config_content) ? template.config_content : [];
      rules.forEach((rule) => {
        const keywordRaw = rule?.["关键词"] ?? rule?.["关键字"];
        const keyword = typeof keywordRaw === "string" ? keywordRaw : String(keywordRaw ?? "");
        if (!keywordMap.has(keyword)) {
          keywordMap.set(keyword, [templateName]);
          return;
        }
        const names = keywordMap.get(keyword);
        if (!names.includes(templateName)) {
          names.push(templateName);
        }
        conflictMap.set(keyword, [...names]);
      });
    });

    conflicts.value = Array.from(conflictMap.entries()).map(([keyword, templateNames]) => ({
      keyword,
      templateNames,
    }));
  } catch (_error) {
    if (conflictCheckToken.value === token) {
      conflicts.value = [];
    }
  } finally {
    if (conflictCheckToken.value === token) {
      checkingConflicts.value = false;
      checkKeywordCollisionWarnings();
    }
  }
}

async function checkKeywordCollisionWarnings() {
  const hasParams =
    !!form.source_entry_id &&
    form.config_ids.length > 0 &&
    conflicts.value.length === 0 &&
    (uploadedReady.value || asrReady.value);
  if (!hasParams) {
    keywordCollisionWarnings.value = [];
    checkingKeywordCollision.value = false;
    return;
  }

  const token = Date.now();
  keywordCollisionToken.value = token;
  checkingKeywordCollision.value = true;
  try {
    const data = await taskStore.checkKeywordCollision({
      source_entry_id: form.source_entry_id,
      config_ids: [...form.config_ids],
      subtitle_source: form.subtitle_source,
    });
    if (keywordCollisionToken.value !== token) return;
    keywordCollisionWarnings.value = Array.isArray(data.warnings) ? data.warnings : [];
    rebuildGroupOrders();
  } catch (_error) {
    if (keywordCollisionToken.value !== token) return;
    keywordCollisionWarnings.value = [];
  } finally {
    if (keywordCollisionToken.value === token) {
      checkingKeywordCollision.value = false;
    }
  }
}

watch(
  () => form.config_ids.slice(),
  () => {
    checkConflicts();
  }
);

watch(
  () => form.source_entry_id,
  () => {
    if (!uploadedReady.value && asrReady.value) {
      form.subtitle_source = "asr";
      checkKeywordCollisionWarnings();
      return;
    }
    if (form.subtitle_source === "uploaded" && !uploadedReady.value && asrReady.value) {
      form.subtitle_source = "asr";
      checkKeywordCollisionWarnings();
      return;
    }
    if (form.subtitle_source === "asr" && !asrReady.value && uploadedReady.value) {
      form.subtitle_source = "uploaded";
    }
    checkKeywordCollisionWarnings();
  }
);

watch(
  () => form.subtitle_source,
  (value) => {
    if (!form.source_entry_id) {
      keywordCollisionWarnings.value = [];
      return;
    }

    if (value === "uploaded" && !uploadedReady.value) {
      if (asrReady.value) {
        form.subtitle_source = "asr";
        ElMessage.warning("当前条目将使用“ASR SRT”（已就绪）");
      } else {
        ElMessage.warning("当前条目暂无可用字幕，请等待ASR完成");
      }
      return;
    }
    if (value === "asr" && !asrReady.value) {
      if (uploadedReady.value) {
        form.subtitle_source = "uploaded";
        ElMessage.warning("当前条目暂无可用ASR字幕，已自动切换到“用户上传SRT”");
      } else {
        ElMessage.warning("当前条目暂无可用字幕，请等待ASR完成");
      }
    }
    checkKeywordCollisionWarnings();
  }
);

watch(
  () => props.modelValue,
  (visible) => {
    if (!visible) {
      resetForm();
    }
  }
);

watch(
  () => keywordCollisionWarnings.value,
  () => {
    rebuildGroupOrders();
  },
  { deep: true }
);

async function submit() {
  if (!canSubmit.value) return;
  submitting.value = true;
  try {
    await emit("submit", {
      task_name: form.task_name,
      source_entry_id: form.source_entry_id,
      subtitle_source: form.subtitle_source,
      add_subtitle_to_video: !!form.add_subtitle_to_video,
      config_ids: [...form.config_ids],
      collision_priority: { ...collisionPriorityPayload.value },
    });
    resetForm();
    open.value = false;
  } finally {
    submitting.value = false;
  }
}
</script>
