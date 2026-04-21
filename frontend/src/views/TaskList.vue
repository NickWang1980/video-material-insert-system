<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <el-button type="primary" @click="createOpen = true">新建任务</el-button>
    </div>

    <div class="flex items-center gap-2">
      <el-select v-model="status" placeholder="状态筛选" style="width: 220px" @change="reload">
        <el-option label="全部" value="" />
        <el-option label="待处理" value="pending" />
        <el-option label="处理中" value="processing" />
        <el-option label="已停止" value="stopped" />
        <el-option label="已完成" value="completed" />
        <el-option label="失败" value="failed" />
      </el-select>
      <el-button @click="reload">刷新</el-button>
    </div>

    <TaskTable
      :items="taskStore.items"
      @open="goDetail"
      @retry="retry"
      @stop="stop"
      @remove="remove"
    />

    <CreateTaskModal
      v-model="createOpen"
      :templates="templates"
      :source-entries="sourceEntries"
      @submit="onSubmit"
    />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";

import TaskTable from "../components/task/TaskTable.vue";
import CreateTaskModal from "../components/task/CreateTaskModal.vue";
import { useTaskStore } from "../store/modules/task";
import { useConfigStore } from "../store/modules/config";
import { useSourceVideoStore } from "../store/modules/sourceVideo";

const REFRESH_INTERVAL_MS = 3000;

const router = useRouter();
const taskStore = useTaskStore();
const configStore = useConfigStore();
const sourceVideoStore = useSourceVideoStore();

const status = ref("");
const createOpen = ref(false);
const templates = computed(() => configStore.templates);
const sourceEntries = computed(() => sourceVideoStore.items);
const pollTimer = ref(null);

const hasRunningTasks = computed(() =>
  taskStore.items.some((item) => item.status === "pending" || item.status === "processing")
);

onMounted(async () => {
  await Promise.all([
    configStore.fetchTemplates(),
    sourceVideoStore.fetchList(),
    reload(),
  ]);
});

onBeforeUnmount(() => {
  stopPolling();
});

watch(hasRunningTasks, (running) => {
  if (running) {
    startPolling();
  } else {
    stopPolling();
  }
});

watch(createOpen, (open) => {
  if (open) {
    sourceVideoStore.fetchList();
  }
});

async function reload() {
  await taskStore.fetchList({ status: status.value || undefined });
}

function startPolling() {
  if (pollTimer.value) return;
  pollTimer.value = setInterval(() => {
    Promise.all([reload(), sourceVideoStore.fetchList()]);
  }, REFRESH_INTERVAL_MS);
}

function stopPolling() {
  if (!pollTimer.value) return;
  clearInterval(pollTimer.value);
  pollTimer.value = null;
}

function goDetail(id) {
  router.push(`/tasks/${id}`);
}

async function retry(id) {
  await taskStore.retry(id);
  ElMessage.success("已重试");
  await reload();
}

async function stop(id) {
  const resp = await taskStore.stop(id);
  ElMessage.success(resp.message || "已发送停止指令");
  await reload();
}

async function remove(id) {
  await taskStore.remove(id);
  await reload();
  ElMessage.success("已删除");
}

async function onSubmit(payload) {
  await taskStore.create(payload);
  ElMessage.success("任务已创建");
  await Promise.all([reload(), sourceVideoStore.fetchList()]);
}
</script>
