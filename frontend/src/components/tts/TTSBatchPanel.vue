<template>
  <el-card class="tts-batch-panel" shadow="never">
    <template #header>
      <span class="font-medium">{{ t("tts.batch.title") }}</span>
    </template>

    <div class="flex flex-col gap-3">
      <!-- 上传区 -->
      <el-upload
        :auto-upload="false"
        :show-file-list="false"
        accept=".txt"
        :on-change="onFileChange"
        :disabled="running"
        drag
      >
        <div class="flex flex-col items-center py-3">
          <el-icon size="28" class="text-gray-400 mb-1"><UploadFilled /></el-icon>
          <span class="text-sm text-gray-600">{{ t("tts.batch.uploadHint") }}</span>
          <span v-if="fileName" class="text-xs text-gray-400 mt-1">{{ fileName }}.txt</span>
        </div>
      </el-upload>

      <!-- 行数 + 预览 -->
      <div v-if="lines.length > 0" class="flex flex-col gap-2">
        <div class="text-sm text-gray-700">
          {{ t("tts.batch.lineCount", { count: lines.length }) }}
        </div>
      </div>

      <!-- 控制按钮 -->
      <div class="flex items-center gap-2">
        <el-button
          type="primary"
          :disabled="running || lines.length === 0"
          @click="onStart"
        >
          {{ t("tts.batch.start") }}
        </el-button>
        <el-button
          type="warning"
          :disabled="!running"
          @click="onStop"
        >
          {{ t("tts.batch.stop") }}
        </el-button>
        <el-button
          v-if="!running && successItems.length > 0"
          type="success"
          @click="onDownloadZip"
        >
          {{ t("tts.batch.downloadZip") }}
        </el-button>
      </div>

      <!-- 进度 -->
      <div v-if="lines.length > 0" class="flex flex-col gap-1">
        <div class="text-xs text-gray-500">
          {{ t("tts.batch.progress", { done: doneCount, total: lines.length }) }}
        </div>
        <el-progress
          :percentage="progressPercent"
          :status="running ? '' : (doneCount === lines.length ? 'success' : '')"
        />
      </div>

      <!-- 行状态表 -->
      <el-table
        v-if="lines.length > 0"
        :data="displayLines"
        size="small"
        border
        max-height="360"
      >
        <el-table-column prop="index" label="#" width="60" />
        <el-table-column :label="t('tts.input.textLabel')" min-width="200">
          <template #default="{ row }">
            <span v-if="row.placeholder" class="text-gray-400">…</span>
            <span v-else>{{ truncate(row.text, 30) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="Status" width="110">
          <template #default="{ row }">
            <span v-if="row.placeholder" class="text-gray-400">—</span>
            <el-tag
              v-else
              :type="statusTag(row.status)"
              size="small"
              effect="plain"
            >
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Duration" width="100">
          <template #default="{ row }">
            <span v-if="row.placeholder">—</span>
            <span v-else-if="row.duration > 0">{{ row.duration.toFixed(1) }}s</span>
            <span v-else>—</span>
          </template>
        </el-table-column>
        <el-table-column label="Error" min-width="160">
          <template #default="{ row }">
            <span v-if="row.placeholder">—</span>
            <span v-else-if="row.error" class="text-red-500 text-xs">{{ row.error }}</span>
            <span v-else>—</span>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </el-card>
</template>

<script setup>
import { ref, computed } from "vue";
import JSZip from "jszip";
import { ElMessage } from "element-plus";
import { UploadFilled } from "@element-plus/icons-vue";
import { useI18n } from "vue-i18n";
import * as ttsApi from "../../api/tts";

const { t } = useI18n();

const lines = ref([]); // Array<{ text, status, audioUrl, duration, error }>
const running = ref(false);
const stopFlag = ref(false);
const fileName = ref("");

const doneCount = computed(
  () =>
    lines.value.filter((l) => l.status === "done" || l.status === "error")
      .length
);

const successItems = computed(() =>
  lines.value.filter((l) => l.status === "done")
);

const progressPercent = computed(() => {
  if (lines.value.length === 0) return 0;
  return Math.round((doneCount.value / lines.value.length) * 100);
});

// 表格仅显示前 10 行 + 占位行（未完成时只展示前 10），完成后展示全部
const displayLines = computed(() => {
  const all = lines.value.map((l, i) => ({ ...l, index: i + 1 }));
  if (all.length <= 10) return all;
  // 全部完成或正在跑：完整列表；初始预览阶段：前 10 + 省略行
  if (running.value || doneCount.value > 0) {
    return all;
  }
  return [
    ...all.slice(0, 10),
    { index: "", text: "", status: "", placeholder: true, duration: 0, error: "" },
  ];
});

async function onFileChange(uploadFile) {
  const raw = uploadFile?.raw;
  if (!raw) return;
  try {
    const text = await raw.text();
    lines.value = text
      .split(/\r?\n/)
      .map((s) => s.trim())
      .filter(Boolean)
      .map((line) => ({
        text: line,
        status: "pending",
        audioUrl: "",
        duration: 0,
        error: "",
      }));
    fileName.value = (raw.name || "tts_batch").replace(/\.txt$/i, "");
  } catch (e) {
    ElMessage.error(t("tts.common.error", { msg: e?.message || String(e) }));
  }
}

// 当前正在跑的合成请求 controller — onStop 用它 abort()
let abortController = null;

async function onStart() {
  if (running.value || lines.value.length === 0) return;
  running.value = true;
  stopFlag.value = false;
  try {
    for (let i = 0; i < lines.value.length; i++) {
      if (stopFlag.value) break;
      const item = lines.value[i];
      if (item.status === "done") continue; // 断点续做
      item.status = "processing";
      item.error = "";
      abortController = new AbortController();
      try {
        const resp = await ttsApi.synthesizeTTS(
          {
            text: item.text,
            language: "auto",
            emotion: "neutral",
            speed: 1.0,
          },
          { signal: abortController.signal }
        );
        item.audioUrl = resp?.audio_url ?? "";
        item.duration =
          typeof resp?.duration_sec === "number" ? resp.duration_sec : 0;
        item.status = "done";
      } catch (e) {
        // axios 把 AbortController.abort() 报成 CanceledError / ERR_CANCELED
        const aborted =
          e?.name === "CanceledError" ||
          e?.code === "ERR_CANCELED" ||
          e?.message === "canceled" ||
          stopFlag.value;
        if (aborted) {
          item.status = "pending";
          item.error = "";
          break;
        }
        item.status = "error";
        item.error = e?.message || String(e);
      } finally {
        abortController = null;
      }
    }
  } finally {
    running.value = false;
  }
}

function onStop() {
  stopFlag.value = true;
  if (abortController) {
    try {
      abortController.abort();
    } catch {
      // ignore — controller 已经 abort 过或失效
    }
  }
}

async function onDownloadZip() {
  if (successItems.value.length === 0) {
    ElMessage.warning(t("tts.batch.lineStatus.pending"));
    return;
  }
  const zip = new JSZip();
  let added = 0;
  for (let i = 0; i < lines.value.length; i++) {
    const item = lines.value[i];
    if (item.status !== "done" || !item.audioUrl) continue;
    try {
      const url = ttsApi.getTTSAudioUrl(item.audioUrl);
      const resp = await fetch(url);
      if (!resp.ok) continue;
      const blob = await resp.blob();
      const safeText = item.text
        .slice(0, 20)
        .replace(/[^\w一-龥]/g, "_");
      const wavName = `${String(i + 1).padStart(3, "0")}_${safeText || "line"}.wav`;
      zip.file(wavName, blob);
      added += 1;
    } catch {
      // 跳过单条失败
    }
  }
  if (added === 0) {
    ElMessage.warning(t("tts.batch.lineStatus.error"));
    return;
  }
  const zipBlob = await zip.generateAsync({ type: "blob" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(zipBlob);
  a.download = `${fileName.value || "tts_batch"}.zip`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(a.href);
}

function statusLabel(s) {
  if (!s) return "";
  return t(`tts.batch.lineStatus.${s}`);
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

function truncate(text, maxLen) {
  if (!text) return "";
  return text.length > maxLen ? `${text.slice(0, maxLen)}…` : text;
}
</script>

<style scoped>
.tts-batch-panel :deep(.el-upload-dragger) {
  padding: 12px;
}
</style>
