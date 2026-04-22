<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-bold">源视频库</h1>
      <el-button type="primary" @click="createOpen = true">新建源视频条目</el-button>
    </div>
    <div class="text-sm text-gray-500">
      SRT 不是必填；未上传时系统会自动启动模型识别字幕并生成与条目同名的 `.srt`。
    </div>

    <el-table :data="sourceVideoStore.items" stripe style="width: 100%">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="name" label="条目名称" min-width="220" />
      <el-table-column label="视频比例" width="120">
        <template #default="{ row }">{{ row.video_aspect_ratio }}</template>
      </el-table-column>
      <el-table-column label="视频像素" width="150">
        <template #default="{ row }">{{ row.video_width }}×{{ row.video_height }}</template>
      </el-table-column>
      <el-table-column label="总时长" width="120">
        <template #default="{ row }">{{ formatDuration(row.video_duration_seconds) }}</template>
      </el-table-column>
      <el-table-column label="音轨" min-width="220">
        <template #default="{ row }">
          <div class="flex items-center gap-2">
            <el-tag :type="hasWav(row) ? 'success' : 'info'" size="small">WAV</el-tag>
            <el-button size="small" text :disabled="!hasWav(row)" @click="downloadAudio(row, 'wav')">
              下载
            </el-button>
            <el-tag :type="hasFlac(row) ? 'success' : 'info'" size="small">FLAC</el-tag>
            <el-button size="small" text :disabled="!hasFlac(row)" @click="downloadAudio(row, 'flac')">
              下载
            </el-button>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="字幕识别" min-width="320">
        <template #default="{ row }">
          <div class="space-y-2">
            <div class="flex items-center gap-2">
              <el-tag :type="hasUploadedSrt(row) ? 'success' : 'info'" size="small">
                上传SRT {{ subtitleCountText(row, "uploaded") }}
              </el-tag>
              <el-button
                size="small"
                text
                :disabled="!hasUploadedSrt(row)"
                @click="previewSubtitle(row, 'uploaded')"
              >
                预览
              </el-button>
              <el-button
                size="small"
                text
                :disabled="!hasUploadedSrt(row)"
                @click="downloadSubtitle(row, 'uploaded')"
              >
                下载
              </el-button>
            </div>
            <div class="flex items-center gap-2">
              <el-tag :type="asrTagType(row)" size="small">
                ASR {{ asrStatusText(row) }} {{ subtitleCountText(row, "asr") }}
              </el-tag>
              <span class="text-xs text-gray-500">{{ asrRetryText(row) }}</span>
              <el-button
                size="small"
                text
                :disabled="!hasAsrSrt(row)"
                @click="previewSubtitle(row, 'asr')"
              >
                预览
              </el-button>
              <el-button
                size="small"
                text
                :disabled="!hasAsrSrt(row)"
                @click="downloadSubtitle(row, 'asr')"
              >
                下载
              </el-button>
              <el-button
                size="small"
                text
                :disabled="row.asr_status === 'running'"
                @click="retryAsr(row)"
              >
                重试识别
              </el-button>
            </div>
            <el-progress
              :percentage="asrProgressValue(row)"
              :status="asrProgressStatus(row)"
              :stroke-width="14"
              :show-text="true"
              :class="asrProgressBarClass(row)"
            />
            <div v-if="row.asr_error" class="text-xs text-red-500 truncate" :title="row.asr_error">
              失败原因：{{ row.asr_error }}
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" min-width="190">
        <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="220">
        <template #default="{ row }">
          <div class="flex items-center gap-2">
            <el-button size="small" @click="renameEntry(row)">重命名</el-button>
            <el-button size="small" type="danger" @click="deleteEntry(row.id)">删除</el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="createOpen" title="新建源视频条目" width="720px">
      <div class="space-y-4">
        <div>
          <div class="text-sm font-medium mb-2">条目名称（可选）</div>
          <el-input v-model="createForm.name" placeholder="不填将自动生成：源视频_YYYYMMDD_HHMMSS" />
        </div>
        <div>
          <div class="text-sm font-medium mb-2">原视频文件</div>
          <FileUpload
            title="拖拽或点击上传视频"
            hint="支持 MP4/MOV 等主流格式"
            accept="video/*"
            :limit="1"
            @update:files="(files) => (createForm.video = files?.[0] || null)"
          />
        </div>
        <div>
          <div class="text-sm font-medium mb-2">SRT字幕文件（可选）</div>
          <FileUpload
            title="拖拽或点击上传 SRT（可不传）"
            hint="不上传时将自动开始模型识别字幕"
            accept=".srt"
            :limit="1"
            @update:files="(files) => (createForm.subtitle = files?.[0] || null)"
          />
        </div>
      </div>
      <template #footer>
        <div class="flex items-center justify-end gap-2">
          <el-button @click="createOpen = false">取消</el-button>
          <el-button type="primary" :loading="creating" @click="submitCreate">创建</el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog v-model="previewOpen" :title="previewTitle" width="760px">
      <div v-loading="sourceVideoStore.subtitlePreviewLoading" class="space-y-3">
        <div class="text-sm text-gray-500">总行数：{{ previewTotal }}</div>
        <el-scrollbar height="420px">
          <div class="space-y-2">
            <div
              v-for="line in previewLines"
              :key="`${line.index}-${line.start}-${line.end}`"
              class="p-3 rounded-lg border border-gray-200 bg-white"
            >
              <div class="text-xs text-gray-500 mb-1">
                #{{ line.index }} · {{ line.start }} → {{ line.end }}
              </div>
              <div class="text-sm whitespace-pre-wrap break-words">{{ line.text }}</div>
            </div>
          </div>
        </el-scrollbar>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import FileUpload from "../components/common/FileUpload.vue";
import { useSourceVideoStore } from "../store/modules/sourceVideo";

const sourceVideoStore = useSourceVideoStore();

const createOpen = ref(false);
const creating = ref(false);
const refreshTimer = ref(null);
const previewOpen = ref(false);
const previewTitle = ref("字幕预览");
const previewTotal = ref(0);
const previewLines = ref([]);
const createForm = reactive({
  name: "",
  video: null,
  subtitle: null,
});

onMounted(() => {
  sourceVideoStore.fetchList();
});

onBeforeUnmount(() => {
  stopRefreshTimer();
});

const hasActiveAsr = computed(() =>
  sourceVideoStore.items.some((item) => item.asr_status === "pending" || item.asr_status === "running")
);

watch(hasActiveAsr, (active) => {
  if (active) {
    startRefreshTimer();
  } else {
    stopRefreshTimer();
  }
});

function resetCreateForm() {
  createForm.name = "";
  createForm.video = null;
  createForm.subtitle = null;
}

async function submitCreate() {
  if (!createForm.video) {
    ElMessage.warning("请先上传视频文件");
    return;
  }

  if (!createForm.subtitle) {
    try {
      await ElMessageBox.confirm(
        "你没有上传SRT，系统将开始用模型识别视频字幕，并生成与条目同名的 .srt 文件。是否继续？",
        "未上传SRT",
        { type: "warning", confirmButtonText: "继续创建", cancelButtonText: "返回上传SRT" }
      );
    } catch (_error) {
      return;
    }
  }

  creating.value = true;
  try {
    await sourceVideoStore.create({
      name: createForm.name.trim() || undefined,
      video: createForm.video,
      subtitle: createForm.subtitle || undefined,
    });
    ElMessage.success("源视频条目已创建");
    createOpen.value = false;
    resetCreateForm();
    await sourceVideoStore.fetchList();
  } catch (error) {
    ElMessage.error(error.message || "创建失败");
  } finally {
    creating.value = false;
  }
}

async function renameEntry(entry) {
  try {
    const { value } = await ElMessageBox.prompt("请输入新的条目名称", "重命名", {
      inputValue: entry.name,
    });
    const name = (value || "").trim();
    if (!name) {
      ElMessage.warning("名称不能为空");
      return;
    }
    await sourceVideoStore.rename(entry.id, name);
    ElMessage.success("已重命名");
    await sourceVideoStore.fetchList();
  } catch (error) {
    if (error === "cancel" || error === "close") return;
    ElMessage.error(error.message || "重命名失败");
  }
}

async function deleteEntry(id) {
  try {
    await ElMessageBox.confirm("确认删除该源视频条目？", "删除确认", { type: "warning" });
    await sourceVideoStore.remove(id);
    ElMessage.success("已删除");
    await sourceVideoStore.fetchList();
  } catch (error) {
    if (error === "cancel" || error === "close") return;
    ElMessage.error(error.message || "删除失败");
  }
}

function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function formatDuration(value) {
  const seconds = Number(value);
  if (!Number.isFinite(seconds) || seconds < 0) return "--:--";
  const total = Math.floor(seconds);
  const minutes = Math.floor(total / 60);
  const remain = total % 60;
  return `${String(minutes).padStart(2, "0")}:${String(remain).padStart(2, "0")}`;
}

function startRefreshTimer() {
  if (refreshTimer.value) return;
  refreshTimer.value = setInterval(() => {
    sourceVideoStore.fetchList();
  }, 4000);
}

function stopRefreshTimer() {
  if (!refreshTimer.value) return;
  clearInterval(refreshTimer.value);
  refreshTimer.value = null;
}

function asrStatusText(row) {
  const status = row.asr_status || "pending";
  if (status === "completed") return "已完成";
  if (status === "running") return "处理中";
  if (status === "failed") return "失败";
  return "待处理";
}

function asrTagType(row) {
  const status = row.asr_status || "pending";
  if (status === "completed") return "success";
  if (status === "running") return "warning";
  if (status === "failed") return "danger";
  return "info";
}

function asrRetryText(row) {
  const retryCount = Number(row.asr_retry_count ?? 0);
  const retryMax = Number(row.asr_retry_max ?? 3);
  if (!Number.isFinite(retryCount) || !Number.isFinite(retryMax)) {
    return "";
  }
  return `重试 ${retryCount}/${retryMax}`;
}

function asrProgressValue(row) {
  const status = row.asr_status || "pending";
  const raw = Number(row.asr_progress ?? 0);
  const safe = Number.isFinite(raw) ? raw : 0;

  if (status === "completed" || hasAsrSrt(row)) return 100;
  if (status === "failed") return Math.max(1, Math.min(100, safe || 100));
  if (status === "running") return Math.max(1, Math.min(99, safe || 35));
  return Math.max(1, Math.min(95, safe || 10));
}

function asrProgressStatus(row) {
  const status = row.asr_status || "pending";
  if (status === "completed" || hasAsrSrt(row)) return "success";
  if (status === "failed") return "exception";
  return "";
}

function asrProgressBarClass(row) {
  const status = row.asr_status || "pending";
  return status === "running" || status === "pending" ? "asr-progress-breathing" : "";
}

function hasWav(row) {
  if (typeof row.has_wav === "boolean") return row.has_wav;
  return !!row.audio_wav_path;
}

function hasFlac(row) {
  if (typeof row.has_flac === "boolean") return row.has_flac;
  return !!row.audio_flac_path;
}

function hasUploadedSrt(row) {
  if (typeof row.has_uploaded_srt === "boolean") return row.has_uploaded_srt;
  return Number.isFinite(Number(row.subtitle_line_count_user));
}

function hasAsrSrt(row) {
  if (typeof row.has_asr_srt === "boolean") return row.has_asr_srt;
  return !!row.asr_srt_path;
}

function subtitleCountText(row, source) {
  const toCountText = (value) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? `(${parsed}行)` : "";
  };

  if (source === "asr") {
    return toCountText(row.subtitle_line_count_asr);
  }
  return toCountText(row.subtitle_line_count_user);
}

function downloadAudio(row, format) {
  window.open(sourceVideoStore.audioDownloadUrl(row.id, format), "_blank");
}

function downloadSubtitle(row, source) {
  if (source === "uploaded" && !hasUploadedSrt(row)) {
    ElMessage.warning("当前条目未上传SRT");
    return;
  }
  if (source === "asr" && !hasAsrSrt(row)) {
    ElMessage.warning("当前条目暂无 ASR SRT");
    return;
  }
  window.open(sourceVideoStore.subtitleDownloadUrl(row.id, source), "_blank");
}

async function previewSubtitle(row, source) {
  if (source === "uploaded" && !hasUploadedSrt(row)) {
    ElMessage.warning("当前条目未上传SRT");
    return;
  }
  if (source === "asr" && !hasAsrSrt(row)) {
    ElMessage.warning("当前条目暂无 ASR SRT");
    return;
  }

  previewTitle.value = `${row.name} · ${source === "asr" ? "ASR SRT" : "上传SRT"} 识别预览`;
  previewTotal.value = 0;
  previewLines.value = [];
  previewOpen.value = true;

  try {
    const payload = await sourceVideoStore.getParsedSubtitle(row.id, source);
    const lines = normalizeParsedLines(payload);
    previewLines.value = lines;
    previewTotal.value = resolveSubtitleTotal(payload, lines.length);
  } catch (error) {
    ElMessage.error(error.message || "字幕预览加载失败");
  }
}

async function retryAsr(row) {
  try {
    await sourceVideoStore.retryAsr(row.id);
    ElMessage.success("已触发ASR重试");
    await sourceVideoStore.fetchList();
  } catch (error) {
    ElMessage.error(error.message || "ASR重试失败");
  }
}

function resolveSubtitleTotal(payload, fallback) {
  if (typeof payload?.total === "number") return payload.total;
  if (typeof payload?.line_count === "number") return payload.line_count;
  if (typeof payload?.count === "number") return payload.count;
  return fallback;
}

function normalizeParsedLines(payload) {
  const rows = Array.isArray(payload?.lines)
    ? payload.lines
    : Array.isArray(payload?.items)
      ? payload.items
      : Array.isArray(payload)
        ? payload
        : [];

  return rows.map((item, idx) => ({
    index: item.index ?? item.no ?? idx + 1,
    start: item.start ?? item.start_time ?? "-",
    end: item.end ?? item.end_time ?? "-",
    text: item.text ?? item.content ?? "",
  }));
}
</script>

<style scoped>
:deep(.asr-progress-breathing .el-progress-bar__inner) {
  animation: asr-breathing 1.8s ease-in-out infinite;
  box-shadow: 0 0 10px rgba(37, 99, 235, 0.4);
}

@keyframes asr-breathing {
  0% {
    opacity: 0.65;
    filter: saturate(0.9);
  }
  50% {
    opacity: 1;
    filter: saturate(1.2);
  }
  100% {
    opacity: 0.65;
    filter: saturate(0.9);
  }
}
</style>
