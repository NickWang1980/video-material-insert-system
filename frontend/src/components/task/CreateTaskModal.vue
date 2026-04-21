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
        <div class="text-xs text-gray-500 mt-2">
          任务创建仅支持多模板合并；如多个模板存在同一关键词，将阻止提交。
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
</template>

<script setup>
import { computed, reactive, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { useConfigStore } from "../../store/modules/config";

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  templates: { type: Array, default: () => [] },
  sourceEntries: { type: Array, default: () => [] },
});
const emit = defineEmits(["update:modelValue", "submit"]);

const configStore = useConfigStore();

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

const submitting = ref(false);
const conflicts = ref([]);
const checkingConflicts = ref(false);
const conflictCheckToken = ref(0);

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

const canSubmit = computed(
  () =>
    !!form.task_name &&
    !!form.source_entry_id &&
    (uploadedReady.value || asrReady.value) &&
    form.config_ids.length > 0 &&
    conflicts.value.length === 0 &&
    !checkingConflicts.value
);

function resetForm() {
  form.task_name = "";
  form.source_entry_id = null;
  form.subtitle_source = "uploaded";
  form.add_subtitle_to_video = false;
  form.config_ids = [];
  conflicts.value = [];
  checkingConflicts.value = false;
}

async function checkConflicts() {
  const ids = [...form.config_ids];
  conflicts.value = [];
  if (ids.length === 0) return;

  const token = Date.now();
  conflictCheckToken.value = token;
  checkingConflicts.value = true;
  try {
    const templates = await Promise.all(ids.map((id) => configStore.getTemplate(id)));
    if (conflictCheckToken.value !== token) return;

    const keywordMap = new Map();
    const conflictMap = new Map();

    templates.forEach((template) => {
      const templateName = template.template_name;
      const rules = Array.isArray(template.config_content) ? template.config_content : [];
      rules.forEach((rule) => {
        const keywordRaw = rule?.["关键字"];
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
      return;
    }
    if (form.subtitle_source === "uploaded" && !uploadedReady.value && asrReady.value) {
      form.subtitle_source = "asr";
      return;
    }
    if (form.subtitle_source === "asr" && !asrReady.value && uploadedReady.value) {
      form.subtitle_source = "uploaded";
    }
  }
);

watch(
  () => form.subtitle_source,
  (value) => {
    if (!form.source_entry_id) {
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
    });
    resetForm();
    open.value = false;
  } finally {
    submitting.value = false;
  }
}
</script>
