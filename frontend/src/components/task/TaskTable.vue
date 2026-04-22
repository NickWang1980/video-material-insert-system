<template>
  <el-table :data="items" stripe style="width: 100%">
    <el-table-column prop="id" label="ID" width="80" />
    <el-table-column prop="task_name" label="任务名称" min-width="180" />
    <el-table-column label="状态" width="120">
      <template #default="{ row }">
        <StatusTag :status="row.status" />
      </template>
    </el-table-column>
    <el-table-column label="进度" width="220">
      <template #default="{ row }">
        <div class="space-y-1">
          <ProgressBar :percent="row.progress" :status="row.status" />
          <div class="text-xs text-gray-600">{{ normalizedPercent(row.progress) }}%</div>
        </div>
      </template>
    </el-table-column>
    <el-table-column label="耗费时间" width="120">
      <template #default="{ row }">
        <span class="text-sm text-gray-700">{{ formatElapsed(row) }}</span>
      </template>
    </el-table-column>
    <el-table-column label="操作" width="620">
      <template #default="{ row }">
        <div class="flex flex-wrap items-center gap-2">
          <el-button size="small" @click="$emit('open', row.id)">详情</el-button>
          <el-button size="small" :disabled="row.status === 'processing'" @click="$emit('retry', row.id)">
            重试
          </el-button>
          <el-button size="small" type="warning" :disabled="!canStop(row.status)" @click="$emit('stop', row.id)">
            停止
          </el-button>
          <el-button size="small" :disabled="!row.output_path" @click="onPlayOutput(row)">播放</el-button>
          <a
            :href="downloadOutputUrl(row.id)"
            target="_blank"
            :class="linkClass(!!row.output_path)"
            @click.prevent="onDownloadOutput(row)"
          >
            下载成品
          </a>
          <a
            :href="downloadReportUrl(row.id)"
            target="_blank"
            :class="linkClass(!!row.report_path)"
            @click.prevent="onDownloadReport(row)"
          >
            下载报告
          </a>
          <a :href="downloadLogUrl(row.id)" target="_blank" class="text-sm underline">下载日志</a>
          <el-button size="small" type="danger" @click="$emit('remove', row.id)">删除</el-button>
        </div>
      </template>
    </el-table-column>
  </el-table>

  <el-dialog
    v-model="previewVisible"
    :title="previewTask ? `预览：${previewTask.task_name}` : '预览'"
    width="720px"
    destroy-on-close
  >
    <div
      v-if="previewTask"
      class="bg-gray-50 rounded-lg p-4 flex items-center justify-center min-h-[320px]"
    >
      <video
        :src="previewUrl"
        class="max-h-[520px] max-w-full"
        controls
        preload="metadata"
      ></video>
    </div>
  </el-dialog>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";

import StatusTag from "../common/StatusTag.vue";
import ProgressBar from "../common/ProgressBar.vue";
import { downloadLogUrl, downloadOutputUrl, downloadReportUrl } from "../../api/task";

defineProps({
  items: { type: Array, required: true },
});
defineEmits(["open", "retry", "remove", "stop"]);

const nowMs = ref(Date.now());
const previewVisible = ref(false);
const previewTask = ref(null);
let tickTimer = null;

const previewUrl = computed(() => {
  if (!previewTask.value) return "";
  return downloadOutputUrl(previewTask.value.id);
});

onMounted(() => {
  tickTimer = setInterval(() => {
    nowMs.value = Date.now();
  }, 1000);
});

onBeforeUnmount(() => {
  if (tickTimer) {
    clearInterval(tickTimer);
    tickTimer = null;
  }
});

function normalizedPercent(value) {
  const number = Number(value || 0);
  if (Number.isNaN(number)) return 0;
  return Math.max(0, Math.min(100, Math.round(number)));
}

function formatElapsed(row) {
  if (!row?.created_at) return "--:--";

  const start = new Date(row.created_at).getTime();
  if (Number.isNaN(start)) return "--:--";

  const end = row.completed_at ? new Date(row.completed_at).getTime() : nowMs.value;
  if (Number.isNaN(end)) return "--:--";

  const totalSeconds = Math.max(0, Math.floor((end - start) / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function canStop(status) {
  return status === "pending" || status === "processing";
}

function linkClass(enabled) {
  if (!enabled) {
    return "text-sm text-gray-400 cursor-not-allowed";
  }
  return "text-sm underline";
}

function onPlayOutput(row) {
  if (!row.output_path) {
    ElMessage.warning("当前任务暂无成品文件");
    return;
  }
  previewTask.value = row;
  previewVisible.value = true;
}

function onDownloadOutput(row) {
  if (!row.output_path) {
    ElMessage.warning("当前任务暂无成品文件");
    return;
  }
  window.open(downloadOutputUrl(row.id), "_blank");
}

function onDownloadReport(row) {
  if (!row.report_path) {
    ElMessage.warning("当前任务暂无报告文件");
    return;
  }
  window.open(downloadReportUrl(row.id), "_blank");
}
</script>
