<template>
  <div class="space-y-8">
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <el-button type="primary" @click="createOpen = true">新建任务</el-button>
        <el-button @click="$router.push('/source-videos')">新建源视频条目</el-button>
      </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-4 gap-6">
      <div class="p-6 rounded-xl border border-gray-200 shadow-card">
        <div class="text-sm text-gray-500">总任务</div>
        <div class="text-2xl font-bold mt-2">{{ stats?.total_tasks ?? "-" }}</div>
      </div>
      <div class="p-6 rounded-xl border border-gray-200 shadow-card">
        <div class="text-sm text-gray-500">已完成</div>
        <div class="text-2xl font-bold mt-2">{{ stats?.completed_tasks ?? "-" }}</div>
      </div>
      <div class="p-6 rounded-xl border border-gray-200 shadow-card">
        <div class="text-sm text-gray-500">处理中</div>
        <div class="text-2xl font-bold mt-2">{{ stats?.processing_tasks ?? "-" }}</div>
      </div>
      <div class="p-6 rounded-xl border border-gray-200 shadow-card">
        <div class="text-sm text-gray-500">素材总数</div>
        <div class="text-2xl font-bold mt-2">{{ stats?.total_materials ?? "-" }}</div>
      </div>
    </div>

    <div class="p-6 rounded-xl border border-gray-200 shadow-card">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-xl font-bold">工作流程</h2>
        <div class="text-sm text-gray-500">先准备素材与模板，再绑定源视频并创建任务</div>
      </div>
      <div class="flex flex-wrap items-stretch gap-3">
        <div class="flow-step">
          <div class="flow-title">① 上传素材</div>
          <div class="flow-desc">图片/GIF/短视频/音效</div>
          <el-button size="small" @click="$router.push('/materials')">去素材库</el-button>
        </div>
        <div class="flow-arrow">→</div>
        <div class="flow-step">
          <div class="flow-title">② 创建模板</div>
          <div class="flow-desc">配置关键词、素材、提示音</div>
          <el-button size="small" @click="$router.push('/configs')">去模板管理</el-button>
        </div>
        <div class="flow-arrow">→</div>
        <div class="flow-step">
          <div class="flow-title">③ 创建源视频条目</div>
          <div class="flow-desc">绑定原视频 + SRT 字幕</div>
          <el-button size="small" @click="$router.push('/source-videos')">去源视频库</el-button>
        </div>
        <div class="flow-arrow">→</div>
        <div class="flow-step">
          <div class="flow-title">④ 新建任务</div>
          <div class="flow-desc">选择源视频条目 + 多模板</div>
          <el-button size="small" type="primary" @click="createOpen = true">立即创建</el-button>
        </div>
        <div class="flow-arrow">→</div>
        <div class="flow-step">
          <div class="flow-title">⑤ 下载产物</div>
          <div class="flow-desc">成品视频 / 报告 / 日志</div>
          <el-button size="small" @click="$router.push('/tasks')">去任务管理</el-button>
        </div>
      </div>
    </div>

    <div>
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-xl font-bold">最近任务</h2>
        <el-button text @click="$router.push('/tasks')">查看全部</el-button>
      </div>
      <TaskTable
        :items="recentTasks"
        @open="goDetail"
        @retry="retry"
        @stop="stop"
        @remove="remove"
      />
    </div>

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

const createOpen = ref(false);
const pollTimer = ref(null);

const stats = computed(() => taskStore.stats);
const recentTasks = computed(() => taskStore.items.slice(0, 5));
const templates = computed(() => configStore.templates);
const sourceEntries = computed(() => sourceVideoStore.items);

const hasRunningTasks = computed(() =>
  taskStore.items.some((item) => item.status === "pending" || item.status === "processing")
);

onMounted(async () => {
  await Promise.all([
    taskStore.fetchStats(),
    taskStore.fetchList({ limit: 5 }),
    configStore.fetchTemplates(),
    sourceVideoStore.fetchList(),
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

function startPolling() {
  if (pollTimer.value) return;
  pollTimer.value = setInterval(async () => {
    await Promise.all([
      taskStore.fetchStats(),
      taskStore.fetchList({ limit: 5 }),
      sourceVideoStore.fetchList(),
    ]);
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
  await Promise.all([taskStore.fetchStats(), taskStore.fetchList({ limit: 5 })]);
}

async function stop(id) {
  const resp = await taskStore.stop(id);
  ElMessage.success(resp.message || "已发送停止指令");
  await Promise.all([taskStore.fetchStats(), taskStore.fetchList({ limit: 5 })]);
}

async function remove(id) {
  await taskStore.remove(id);
  ElMessage.success("已删除");
  await Promise.all([taskStore.fetchStats(), taskStore.fetchList({ limit: 5 })]);
}

async function onSubmit(payload) {
  await taskStore.create(payload);
  ElMessage.success("任务已创建");
  await Promise.all([
    taskStore.fetchStats(),
    taskStore.fetchList({ limit: 5 }),
    sourceVideoStore.fetchList(),
  ]);
}
</script>

<style scoped>
.flow-step {
  flex: 1 1 180px;
  min-width: 180px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  justify-content: space-between;
}

.flow-title {
  font-weight: 700;
}

.flow-desc {
  color: #6b7280;
  font-size: 13px;
  line-height: 1.4;
}

.flow-arrow {
  align-self: center;
  color: #9ca3af;
  font-size: 20px;
  font-weight: 700;
  line-height: 1;
}

@media (max-width: 1024px) {
  .flow-arrow {
    display: none;
  }
}
</style>
