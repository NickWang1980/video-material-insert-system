<template>
  <div class="space-y-8">
    <div class="grid grid-cols-1 md:grid-cols-4 gap-6">
      <div class="px-5 py-3 rounded-xl border border-gray-200 bg-white shadow-card flex items-center justify-between gap-3">
        <div class="text-sm text-gray-500">总任务</div>
        <div class="text-2xl font-bold">{{ stats?.total_tasks ?? "-" }}</div>
      </div>
      <div class="px-5 py-3 rounded-xl border border-gray-200 bg-white shadow-card flex items-center justify-between gap-3">
        <div class="text-sm text-gray-500">已完成</div>
        <div class="text-2xl font-bold">{{ stats?.completed_tasks ?? "-" }}</div>
      </div>
      <div class="px-5 py-3 rounded-xl border border-gray-200 bg-white shadow-card flex items-center justify-between gap-3">
        <div class="text-sm text-gray-500">处理中</div>
        <div class="text-2xl font-bold">{{ stats?.processing_tasks ?? "-" }}</div>
      </div>
      <div class="px-5 py-3 rounded-xl border border-gray-200 bg-white shadow-card flex items-center justify-between gap-3">
        <div class="text-sm text-gray-500">素材总数</div>
        <div class="text-2xl font-bold">{{ stats?.total_materials ?? "-" }}</div>
      </div>
      <div class="px-5 py-3 rounded-xl border border-gray-200 bg-white shadow-card flex items-center justify-between gap-3">
        <div class="text-sm text-gray-500">混剪项目</div>
        <div class="text-2xl font-bold">{{ stats?.total_rough_cut_projects ?? "-" }}</div>
      </div>
      <div class="px-5 py-3 rounded-xl border border-gray-200 bg-white shadow-card flex items-center justify-between gap-3">
        <div class="text-sm text-gray-500">混剪已完成</div>
        <div class="text-2xl font-bold">{{ stats?.completed_rough_cut_projects ?? "-" }}</div>
      </div>
      <div class="px-5 py-3 rounded-xl border border-gray-200 bg-white shadow-card flex items-center justify-between gap-3">
        <div class="text-sm text-gray-500">混剪处理中</div>
        <div class="text-2xl font-bold">{{ stats?.processing_rough_cut_projects ?? "-" }}</div>
      </div>
    </div>

    <div class="p-6 rounded-xl border border-gray-200 shadow-card">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-xl font-bold">工作流程</h2>
        <div class="text-sm text-gray-500">混剪入口或素材插入流水线，按需选择</div>
      </div>
      <div class="flex flex-wrap items-stretch gap-3">
        <div class="flow-step">
          <div class="flow-title">① 混剪</div>
          <div class="flow-desc">多角色剪辑独立入口</div>
          <el-button size="small" type="primary" @click="$router.push('/rough-cut/unit')">去混剪单元</el-button>
        </div>
        <div class="flow-arrow">→</div>
        <div class="flow-step">
          <div class="flow-title">② 上传素材</div>
          <div class="flow-desc">图片/GIF/短视频/音效</div>
          <el-button size="small" @click="$router.push('/materials')">去素材库</el-button>
        </div>
        <div class="flow-arrow">→</div>
        <div class="flow-step">
          <div class="flow-title">③ 创建模板</div>
          <div class="flow-desc">配置关键词、素材、提示音</div>
          <el-button size="small" @click="$router.push('/configs')">去模板管理</el-button>
        </div>
        <div class="flow-arrow">→</div>
        <div class="flow-step">
          <div class="flow-title">④ 创建源视频条目</div>
          <div class="flow-desc">绑定原视频 + SRT 字幕</div>
          <el-button size="small" @click="$router.push('/source-videos')">去源视频库</el-button>
        </div>
        <div class="flow-arrow">→</div>
        <div class="flow-step">
          <div class="flow-title">⑤ 新建任务</div>
          <div class="flow-desc">选择源视频条目 + 多模板</div>
          <el-button size="small" type="primary" @click="createOpen = true">立即创建</el-button>
        </div>
        <div class="flow-arrow">→</div>
        <div class="flow-step">
          <div class="flow-title">⑥ 下载产物</div>
          <div class="flow-desc">成品视频 / 报告 / 日志</div>
          <el-button size="small" @click="$router.push('/tasks')">去任务管理</el-button>
        </div>
      </div>
    </div>

    <div>
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-xl font-bold">最近任务</h2>
        <div class="flex items-center gap-2">
          <el-button text @click="$router.push('/tasks')">素材插入任务</el-button>
          <el-button text @click="$router.push('/rough-cut/unit')">混剪项目</el-button>
        </div>
      </div>
      <el-table :data="recentItems" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column label="类型" width="110">
          <template #default="{ row }">
            <el-tag :type="row.kind === 'rough_cut' ? 'warning' : 'primary'" size="small" effect="light">
              {{ row.kind === 'rough_cut' ? '混剪' : '素材插入' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="名称" prop="name" min-width="220" show-overflow-tooltip />
        <el-table-column label="状态" width="110">
          <template #default="{ row }"><StatusTag :status="row.normalizedStatus" /></template>
        </el-table-column>
        <el-table-column label="进度" width="200">
          <template #default="{ row }">
            <div class="space-y-1">
              <ProgressBar :percent="row.progress" :status="row.normalizedStatus" />
              <div class="text-xs text-gray-600">{{ normalizedPercent(row.progress) }}%</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">
            <span class="text-sm text-gray-700">{{ formatTime(row.createdAt) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="120">
          <template #default="{ row }">
            <el-button size="small" @click="goDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
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

import StatusTag from "../components/common/StatusTag.vue";
import ProgressBar from "../components/common/ProgressBar.vue";
import CreateTaskModal from "../components/task/CreateTaskModal.vue";
import { useTaskStore } from "../store/modules/task";
import { useConfigStore } from "../store/modules/config";
import { useSourceVideoStore } from "../store/modules/sourceVideo";
import { listRoughCutProjects } from "../api/roughCut";

const REFRESH_INTERVAL_MS = 3000;

const router = useRouter();
const taskStore = useTaskStore();
const configStore = useConfigStore();
const sourceVideoStore = useSourceVideoStore();

const createOpen = ref(false);
const pollTimer = ref(null);
const recentRoughCutProjects = ref([]);

const stats = computed(() => taskStore.stats);
const recentTasks = computed(() => taskStore.items.slice(0, 5));
const templates = computed(() => configStore.templates);
const sourceEntries = computed(() => sourceVideoStore.items);

const recentItems = computed(() => {
  const tasks = (recentTasks.value || []).map((t) => ({
    kind: "insert",
    id: t.id,
    name: t.task_name,
    status: t.status,
    normalizedStatus: t.status,
    progress: t.progress,
    createdAt: t.created_at,
  }));
  const projects = (recentRoughCutProjects.value || []).map((p) => ({
    kind: "rough_cut",
    id: p.id,
    name: p.title,
    status: p.status,
    normalizedStatus: _normalizeRoughCutStatus(p),
    progress: p.progress,
    createdAt: p.createdAt,
  }));
  return [...tasks, ...projects]
    .sort((a, b) => _toMs(b.createdAt) - _toMs(a.createdAt))
    .slice(0, 8);
});

const hasRunningTasks = computed(() =>
  taskStore.items.some((item) => item.status === "pending" || item.status === "processing")
);
const hasRunningRoughCut = computed(() =>
  recentRoughCutProjects.value.some((p) => p.status === "processing")
);
const hasAnyRunning = computed(() => hasRunningTasks.value || hasRunningRoughCut.value);

onMounted(async () => {
  await Promise.all([
    taskStore.fetchStats(),
    taskStore.fetchList({ limit: 5 }),
    configStore.fetchTemplates(),
    sourceVideoStore.fetchList(),
    fetchRecentRoughCut(),
  ]);
});

onBeforeUnmount(() => stopPolling());

watch(hasAnyRunning, (running) => (running ? startPolling() : stopPolling()));

watch(createOpen, (open) => {
  if (open) sourceVideoStore.fetchList();
});

async function fetchRecentRoughCut() {
  try {
    const { items } = await listRoughCutProjects(1, 5);
    recentRoughCutProjects.value = items || [];
  } catch (_e) {
    recentRoughCutProjects.value = [];
  }
}

function startPolling() {
  if (pollTimer.value) return;
  pollTimer.value = setInterval(async () => {
    await Promise.all([
      taskStore.fetchStats(),
      taskStore.fetchList({ limit: 5 }),
      sourceVideoStore.fetchList(),
      fetchRecentRoughCut(),
    ]);
  }, REFRESH_INTERVAL_MS);
}

function stopPolling() {
  if (!pollTimer.value) return;
  clearInterval(pollTimer.value);
  pollTimer.value = null;
}

function goDetail(row) {
  if (row.kind === "rough_cut") {
    router.push("/rough-cut/unit");
  } else {
    router.push(`/tasks/${row.id}`);
  }
}

function _normalizeRoughCutStatus(p) {
  const s = String(p.status || "").toLowerCase();
  if (s === "ready" || p.phase === "completed") return "completed";
  if (s === "processing") return "processing";
  if (s === "error") return "failed";
  return "pending";
}

function _toMs(iso) {
  if (!iso) return 0;
  const t = new Date(iso).getTime();
  return Number.isNaN(t) ? 0 : t;
}

function normalizedPercent(value) {
  const n = Number(value || 0);
  if (Number.isNaN(n)) return 0;
  return Math.max(0, Math.min(100, Math.round(n)));
}

function formatTime(iso) {
  if (!iso) return "-";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "-";
  return d.toLocaleString("zh-CN", { hour12: false });
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

<style>
html.dark .flow-step {
  background: #1f2937;
  border-color: #374151;
}

html.dark .flow-desc {
  color: #9ca3af;
}

html.dark .flow-arrow {
  color: #6b7280;
}

html.glass .flow-step {
  background: rgba(255, 255, 255, 0.07) !important;
  border-color: rgba(255, 255, 255, 0.14) !important;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.14);
}

html.glass .flow-desc {
  color: rgba(255, 255, 255, 0.58) !important;
}

html.glass .flow-arrow {
  color: rgba(255, 255, 255, 0.35) !important;
}
</style>
