<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-bold">任务详情 #{{ id }}</h1>
      <div class="flex items-center gap-2">
        <el-button @click="refresh">刷新</el-button>
        <el-button :disabled="task?.status === 'processing'" @click="retry">重试</el-button>
        <el-button
          type="warning"
          :disabled="!canStop(task?.status)"
          @click="stop"
        >
          停止
        </el-button>
        <el-button type="danger" @click="remove">删除</el-button>
      </div>
    </div>

    <div class="p-6 rounded-xl border border-gray-200 shadow-card" v-if="task">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div><div class="text-sm text-gray-500">任务名称</div><div class="font-bold mt-1">{{ task.task_name }}</div></div>
        <div><div class="text-sm text-gray-500">状态</div><div class="mt-1"><StatusTag :status="task.status" /></div></div>
        <div>
          <div class="text-sm text-gray-500">使用模板</div>
          <div class="mt-1 text-sm">
            <span v-if="task.source_templates?.length">
              {{ task.source_templates.map((x) => `${x.name} (#${x.id})`).join("，") }}
            </span>
            <span v-else>-</span>
          </div>
        </div>
        <div>
          <div class="text-sm text-gray-500">源视频条目</div>
          <div class="mt-1 text-sm">
            <span v-if="task.source_video">
              {{ task.source_video.name }} (#{{ task.source_video.id }})
            </span>
            <span v-else>-</span>
          </div>
        </div>
        <div>
          <div class="text-sm text-gray-500">视频比例</div>
          <div class="font-medium mt-1">{{ task.video_aspect_ratio || "-" }}</div>
        </div>
        <div>
          <div class="text-sm text-gray-500">视频像素</div>
          <div class="font-medium mt-1">
            {{ task.video_width && task.video_height ? `${task.video_width}×${task.video_height}` : "-" }}
          </div>
        </div>
        <div>
          <div class="text-sm text-gray-500">进度</div>
          <div class="mt-2"><ProgressBar :percent="task.progress" :status="task.status" /></div>
          <div class="text-xs text-gray-600 mt-1">{{ normalizedPercent(task.progress) }}%</div>
        </div>
        <div class="flex items-end gap-2">
          <a class="text-sm underline" :href="downloadOutputUrl" target="_blank" v-if="task.output_path">下载成品</a>
          <a class="text-sm underline" :href="downloadReportUrl" target="_blank" v-if="task.report_path">下载报告</a>
          <a class="text-sm underline" :href="downloadLogUrl" target="_blank">下载日志</a>
        </div>
      </div>
    </div>

    <div class="p-6 rounded-xl border border-gray-200 shadow-card">
      <div class="font-bold mb-3">处理日志</div>
      <div class="flex items-center justify-between mb-3">
        <div class="text-sm text-gray-500">页面展示的是日志尾部（可用于快速排错）。</div>
        <div class="flex items-center gap-2">
          <el-select v-model="tailKb" size="small" style="width: 140px" @change="loadLog">
            <el-option label="尾部 64KB" :value="64" />
            <el-option label="尾部 256KB" :value="256" />
            <el-option label="尾部 1024KB" :value="1024" />
          </el-select>
          <el-button size="small" @click="loadLog">刷新日志</el-button>
        </div>
      </div>
      <pre class="text-xs bg-gray-50 border border-gray-200 rounded-xl p-4 overflow-auto max-h-[420px] whitespace-pre-wrap">{{ logText }}</pre>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";

import StatusTag from "../components/common/StatusTag.vue";
import ProgressBar from "../components/common/ProgressBar.vue";

import { useTaskStore } from "../store/modules/task";
import {
  downloadLogUrl as taskDownloadLogUrl,
  downloadOutputUrl as taskDownloadOutputUrl,
  downloadReportUrl as taskDownloadReportUrl,
  getLogText,
} from "../api/task";

const REFRESH_INTERVAL_MS = 2000;

const props = defineProps({ id: { type: String, required: true } });
const id = Number(props.id);

const router = useRouter();
const taskStore = useTaskStore();

const task = ref(null);
const logText = ref("");
const tailKb = ref(256);
const pollTimer = ref(null);

const downloadOutputUrl = computed(() => taskDownloadOutputUrl(id));
const downloadReportUrl = computed(() => taskDownloadReportUrl(id));
const downloadLogUrl = computed(() => taskDownloadLogUrl(id));

const isRunning = computed(() => {
  const status = task.value?.status;
  return status === "pending" || status === "processing";
});

onMounted(async () => {
  await refresh();
});

onBeforeUnmount(() => {
  stopPolling();
});

watch(isRunning, (running) => {
  if (running) {
    startPolling();
  } else {
    stopPolling();
  }
});

async function refresh() {
  task.value = await taskStore.fetchOne(id);
  await loadLog();
}

async function refreshRunningTask() {
  task.value = await taskStore.fetchOne(id);
  if (isRunning.value) {
    await loadLog();
  }
}

function startPolling() {
  if (pollTimer.value) return;
  pollTimer.value = setInterval(() => {
    refreshRunningTask();
  }, REFRESH_INTERVAL_MS);
}

function stopPolling() {
  if (!pollTimer.value) return;
  clearInterval(pollTimer.value);
  pollTimer.value = null;
}

async function retry() {
  await taskStore.retry(id);
  ElMessage.success("已重试");
  await refresh();
}

async function stop() {
  const resp = await taskStore.stop(id);
  ElMessage.success(resp.message || "已发送停止指令");
  await refresh();
}

async function remove() {
  await taskStore.remove(id);
  ElMessage.success("已删除");
  router.push("/tasks");
}

async function loadLog() {
  try {
    logText.value = await getLogText(id, tailKb.value);
  } catch (error) {
    logText.value = error.message || "获取日志失败";
  }
}

function canStop(status) {
  return status === "pending" || status === "processing";
}

function normalizedPercent(value) {
  const number = Number(value || 0);
  if (Number.isNaN(number)) return 0;
  return Math.max(0, Math.min(100, Math.round(number)));
}
</script>
