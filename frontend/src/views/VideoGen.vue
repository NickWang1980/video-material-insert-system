<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">视频生成</h1>
        <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">
          基于 heygem 数字人引擎：音频 + 参考视频 → 合成口型对齐的数字人 mp4。
        </p>
      </div>
      <el-tag :type="store.isHealthy ? 'success' : 'warning'" effect="plain">
        Phase-1
      </el-tag>
    </div>

    <!-- Health status -->
    <VideoGenStatusBar
      :health="store.health"
      :loading="store.healthLoading"
      @refresh="store.fetchHealth"
    />

    <!-- Main 3-column layout -->
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
      <!-- LEFT — audio source -->
      <div class="lg:col-span-4 p-4 rounded-xl border border-gray-200 shadow-card">
        <div class="font-bold mb-3 flex items-center gap-2">
          <span>① 音频源</span>
          <el-tag v-if="audioSel" type="success" size="small">已选 {{ audioSel.type }}</el-tag>
        </div>
        <AudioSourcePicker @update:selection="audioSel = $event" />
      </div>

      <!-- MIDDLE — reference video -->
      <div class="lg:col-span-4 p-4 rounded-xl border border-gray-200 shadow-card">
        <div class="font-bold mb-3 flex items-center gap-2">
          <span>② 参考视频</span>
          <el-tag v-if="videoSel" type="success" size="small">已选 {{ videoSel.type }}</el-tag>
        </div>
        <VideoSourcePicker @update:selection="videoSel = $event" />
      </div>

      <!-- RIGHT — task panel -->
      <div class="lg:col-span-4 p-4 rounded-xl border border-gray-200 shadow-card flex flex-col gap-3">
        <div class="font-bold">③ 任务与产物</div>
        <div>
          <div class="text-sm font-medium mb-1">任务名（可选）</div>
          <el-input v-model="taskName" placeholder="如：演员A_5月新品_数字人" maxlength="100" show-word-limit />
        </div>
        <el-button
          type="primary"
          size="large"
          class="!h-10"
          :loading="store.creating"
          :disabled="!canSubmit"
          @click="onSubmit"
        >
          {{ submitLabel }}
        </el-button>

        <!-- Active task display -->
        <div v-if="currentTask" class="mt-2 p-3 rounded-lg border border-gray-100 bg-gray-50 space-y-2">
          <div class="text-sm">
            <span class="font-mono text-xs text-gray-500">#{{ currentTask.id }}</span>
            <el-tag size="small" class="ml-2" :type="statusTagType(currentTask.status)">
              {{ statusLabel(currentTask.status) }}
            </el-tag>
            <span v-if="currentTask.phase" class="text-xs text-gray-500 ml-1">· {{ currentTask.phase }}</span>
          </div>
          <progress
            :value="currentTask.progress || 0"
            max="100"
            class="w-full"
          />
          <div class="text-xs text-gray-500 text-right">{{ currentTask.progress || 0 }}%</div>

          <div v-if="currentTask.error_message" class="text-xs text-red-600 break-all">
            {{ currentTask.error_message }}
          </div>

          <!-- Result preview & actions -->
          <div v-if="currentTask.status === 'succeeded' && currentTask.result_path" class="space-y-2">
            <video :src="downloadUrl(currentTask.id)" controls preload="none" class="w-full rounded border" />
            <div class="flex gap-2 flex-wrap">
              <el-button size="small" type="primary" @click="onDownload">下载 mp4</el-button>
              <el-button size="small" @click="saveDialogOpen = true">保存到素材库</el-button>
              <el-button size="small" @click="$router.push('/rough-cut/unit')">去混剪</el-button>
            </div>
          </div>
          <div v-else-if="!['succeeded', 'failed', 'cancelled', 'interrupted'].includes(currentTask.status)" class="flex gap-2">
            <el-button size="small" type="danger" plain @click="onCancel">取消任务</el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- Recent tasks -->
    <div class="p-4 rounded-xl border border-gray-200 shadow-card">
      <div class="flex items-center justify-between mb-3">
        <div class="font-bold">近期任务（最新 20 条）</div>
        <el-button size="small" @click="store.fetchTasks(20)">刷新</el-button>
      </div>
      <el-table :data="store.tasks" empty-text="暂无任务" style="width: 100%">
        <el-table-column label="ID" width="70" prop="id" />
        <el-table-column label="名称 / 音频源 / 视频源" min-width="280">
          <template #default="{ row }">
            <div class="text-sm">{{ row.task_name || "(未命名)" }}</div>
            <div class="text-xs text-gray-500 mt-0.5">
              audio: {{ row.audio_source_type }}
              <span v-if="row.audio_source_ref">({{ row.audio_source_ref.slice(0, 30) }}...)</span>
              · video: {{ row.video_source_type }}
              <span v-if="row.video_source_ref">({{ row.video_source_ref.slice(0, 20) }}...)</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="进度" width="140">
          <template #default="{ row }">
            <progress :value="row.progress || 0" max="100" class="w-full" />
            <div class="text-xs text-right text-gray-500">{{ row.progress || 0 }}%</div>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">
            <span class="text-xs">{{ formatTime(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" align="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 'succeeded'" size="small" @click="onPreview(row)">预览</el-button>
            <el-button v-else size="small" plain @click="onResume(row)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- Save to material dialog -->
    <SaveVideoToMaterialDialog
      v-model="saveDialogOpen"
      :task-id="currentTask?.id"
      @saved="onMaterialSaved"
    />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { useVideoGenStore } from "../store/modules/videoGen";
import { getVideoGenDownloadUrl } from "../api/videoGen";
import VideoGenStatusBar from "../components/videoGen/VideoGenStatusBar.vue";
import AudioSourcePicker from "../components/videoGen/AudioSourcePicker.vue";
import VideoSourcePicker from "../components/videoGen/VideoSourcePicker.vue";
import SaveVideoToMaterialDialog from "../components/videoGen/SaveVideoToMaterialDialog.vue";

const store = useVideoGenStore();
const audioSel = ref(null);
const videoSel = ref(null);
const taskName = ref("");
const saveDialogOpen = ref(false);

const currentTask = computed(() => store.currentTask);

onMounted(() => {
  store.startHealthPolling(5000);
  store.fetchTasks(20).catch(() => {});
});

onBeforeUnmount(() => {
  store.stopHealthPolling();
  store.stopTaskPolling();
});

const canSubmit = computed(() => {
  if (!store.isHealthy) return false;
  if (!audioSel.value || !videoSel.value) return false;
  // upload requires file present; ref-based requires ref present
  if (audioSel.value.type === "upload" && !audioSel.value.file) return false;
  if (audioSel.value.type !== "upload" && !audioSel.value.ref) return false;
  if (videoSel.value.type === "upload" && !videoSel.value.file) return false;
  if (videoSel.value.type !== "upload" && !videoSel.value.ref) return false;
  return true;
});

const submitLabel = computed(() => {
  if (!store.isHealthy) return "heygem 未就绪";
  if (!audioSel.value) return "请先选音频";
  if (!videoSel.value) return "请先选参考视频";
  return "开始合成";
});

async function onSubmit() {
  if (!canSubmit.value) return;
  const payload = {
    task_name: taskName.value || null,
    audio_source_type: audioSel.value.type,
    audio_source_ref: audioSel.value.type === "upload" ? null : audioSel.value.ref,
    video_source_type: videoSel.value.type,
    video_source_ref: videoSel.value.type === "upload" ? null : videoSel.value.ref,
  };
  try {
    await store.createTask(
      payload,
      audioSel.value.type === "upload" ? audioSel.value.file : null,
      videoSel.value.type === "upload" ? videoSel.value.file : null,
    );
    ElMessage.success("任务已创建，开始合成");
    store.fetchTasks(20).catch(() => {});
  } catch (e) {
    ElMessage.error(`创建失败：${e?.response?.data?.detail || e?.message || e}`);
  }
}

async function onCancel() {
  try {
    await store.cancelCurrent();
    ElMessage.info("已请求取消");
  } catch (e) {
    ElMessage.error(`取消失败：${e?.message || e}`);
  }
}

function downloadUrl(id) {
  return getVideoGenDownloadUrl(id);
}

function onDownload() {
  if (!currentTask.value?.id) return;
  window.open(downloadUrl(currentTask.value.id), "_blank");
}

function onMaterialSaved() {
  ElMessage.success("已写入素材库");
}

function onPreview(row) {
  store.currentTask = row;
  store.startTaskPolling(row.id);  // immediate re-fetch; will auto-stop since terminal
}

function onResume(row) {
  store.currentTask = row;
  if (!["succeeded", "failed", "cancelled", "interrupted"].includes(row.status)) {
    store.startTaskPolling(row.id);
  }
}

function statusTagType(s) {
  return {
    pending: "info",
    running: "warning",
    succeeded: "success",
    failed: "danger",
    cancelled: "info",
    interrupted: "danger",
  }[s] || "info";
}

function statusLabel(s) {
  return {
    pending: "排队中",
    running: "合成中",
    succeeded: "已完成",
    failed: "失败",
    cancelled: "已取消",
    interrupted: "中断",
  }[s] || s;
}

function formatTime(s) {
  if (!s) return "";
  try {
    return new Date(s).toLocaleString();
  } catch {
    return s;
  }
}
</script>
