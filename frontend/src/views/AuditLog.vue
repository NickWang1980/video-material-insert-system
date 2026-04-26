<template>
  <div class="space-y-6">
    <section class="rounded-2xl border border-gray-200 bg-white p-5 shadow-card">
      <div class="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <!-- <div class="text-2xl font-bold tracking-tight">操作历史</div> -->
          <p class="mt-1 text-sm text-gray-500">所有写操作的完整审计记录，包含操作人、时间及行为详情。</p>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <el-button @click="load(1)">刷新</el-button>
          <el-button @click="exportJson" :loading="exporting">导出 JSON</el-button>
          <el-button @click="exportCsv" :loading="exporting">导出 CSV</el-button>
          <el-button v-if="authStore.isAdmin" type="danger" plain @click="confirmClear">清空历史</el-button>
        </div>
      </div>

      <!-- Filters -->
      <div class="mt-5 flex flex-wrap gap-3">
        <el-select
          v-model="filters.entityType"
          clearable
          placeholder="全部类型"
          style="width: 160px"
          @change="load(1)"
        >
          <el-option v-for="t in ENTITY_TYPES" :key="t.value" :label="t.label" :value="t.value" />
        </el-select>

        <el-input
          v-model="filters.operator"
          clearable
          placeholder="操作人"
          style="width: 150px"
          @keyup.enter="load(1)"
          @clear="load(1)"
        />

        <el-date-picker
          v-model="filters.dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
          style="width: 260px"
          @change="load(1)"
        />

        <el-checkbox v-model="filters.videoOnly" label="仅看视频生成" @change="load(1)" />
      </div>
    </section>

    <!-- Table -->
    <section class="rounded-2xl border border-gray-200 bg-white shadow-card overflow-hidden">
      <el-table
        :data="rows"
        v-loading="loading"
        row-key="id"
        stripe
        :row-class-name="rowClass"
        style="width: 100%"
      >
        <el-table-column label="时间" width="175" fixed>
          <template #default="{ row }">
            <span class="text-xs tabular-nums">{{ formatTs(row.createdAt) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" min-width="160">
          <template #default="{ row }">
            <div class="flex items-center gap-2">
              <el-tag
                :type="methodColor(row.method)"
                size="small"
                class="font-mono"
              >{{ row.method }}</el-tag>
              <span class="text-sm font-medium">{{ row.action }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="类型" width="130">
          <template #default="{ row }">
            <el-tag size="small" effect="plain" :type="row.entityType === 'task' ? 'success' : ''">
              {{ ENTITY_LABEL[row.entityType] || row.entityType || '—' }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="对象ID" width="90" align="center">
          <template #default="{ row }">
            <span class="text-xs text-gray-500">{{ row.entityId || '—' }}</span>
          </template>
        </el-table-column>

        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.statusCode < 400 ? 'success' : 'danger'" size="small">
              {{ row.statusCode }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="操作人" width="130">
          <template #default="{ row }">
            <span class="text-sm">{{ row.operator || '—' }}</span>
          </template>
        </el-table-column>

        <el-table-column label="来源IP" width="130">
          <template #default="{ row }">
            <span class="text-xs font-mono text-gray-500">{{ row.ipAddress || '—' }}</span>
          </template>
        </el-table-column>

        <el-table-column label="耗时" width="85" align="right">
          <template #default="{ row }">
            <span class="text-xs text-gray-400">{{ row.durationMs != null ? row.durationMs + 'ms' : '—' }}</span>
          </template>
        </el-table-column>
      </el-table>

      <div class="flex items-center justify-between px-4 py-3 border-t border-gray-100">
        <span class="text-sm text-gray-500">共 {{ total }} 条记录</span>
        <el-pagination
          v-if="total > pageSize"
          background
          layout="prev, pager, next"
          :total="total"
          :page-size="pageSize"
          :current-page="currentPage"
          @current-change="load"
        />
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { listAuditLogs, fetchAllAuditLogs, clearAuditLogs } from "../api/audit";
import { useAuthStore } from "../store/modules/auth";

const authStore = useAuthStore();

const ENTITY_TYPES = [
  { value: "task", label: "任务" },
  { value: "source_video", label: "源视频" },
  { value: "material", label: "素材" },
  { value: "material_product", label: "产品目录" },
  { value: "material_script_folder", label: "脚本文件夹" },
  { value: "config_template", label: "配置模板" },
  { value: "rough_cut_project", label: "混剪项目" },
  { value: "rough_cut_asset", label: "混剪素材" },
  { value: "rough_cut_sentence", label: "分镜句子" },
  { value: "settings", label: "系统设置" },
];

const ENTITY_LABEL = Object.fromEntries(ENTITY_TYPES.map((t) => [t.value, t.label]));

const rows = ref([]);
const total = ref(0);
const currentPage = ref(1);
const pageSize = 20;
const loading = ref(false);

const filters = reactive({
  entityType: "",
  operator: "",
  dateRange: null,
  videoOnly: false,
});

function formatTs(ts) {
  if (!ts) return "—";
  const d = new Date(ts);
  return d.toLocaleString("zh-CN", {
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
    hour12: false,
  });
}

function methodColor(method) {
  return { POST: "success", DELETE: "danger", PUT: "warning", PATCH: "warning" }[method] || "info";
}

function rowClass({ row }) {
  if (row.entityType === "task" && row.statusCode < 400) return "row-highlight-task";
  return "";
}

async function load(page = 1) {
  loading.value = true;
  currentPage.value = page;
  try {
    const params = {
      page,
      pageSize,
      entityType: filters.videoOnly ? "task" : (filters.entityType || undefined),
      operator: filters.operator || undefined,
      startDate: filters.dateRange?.[0] || undefined,
      endDate: filters.dateRange?.[1] || undefined,
    };
    const result = await listAuditLogs(params);
    rows.value = result.items;
    total.value = result.total;
  } finally {
    loading.value = false;
  }
}

const exporting = ref(false);

function _currentExportParams() {
  return {
    entityType: filters.videoOnly ? "task" : (filters.entityType || undefined),
    operator: filters.operator || undefined,
    startDate: filters.dateRange?.[0] || undefined,
    endDate: filters.dateRange?.[1] || undefined,
  };
}

function _downloadFile(content, filename, mime) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function _dateTag() {
  return new Date().toISOString().slice(0, 10);
}

async function exportJson() {
  exporting.value = true;
  try {
    const items = await fetchAllAuditLogs(_currentExportParams());
    _downloadFile(JSON.stringify(items, null, 2), `audit_${_dateTag()}.json`, "application/json");
    ElMessage.success(`已导出 ${items.length} 条记录`);
  } catch {
    ElMessage.error("导出失败");
  } finally {
    exporting.value = false;
  }
}

async function exportCsv() {
  exporting.value = true;
  try {
    const items = await fetchAllAuditLogs(_currentExportParams());
    const headers = ["时间", "方法", "操作", "类型", "对象ID", "状态码", "操作人", "来源IP", "耗时(ms)"];
    const rows = items.map((r) => [
      formatTs(r.createdAt),
      r.method,
      r.action,
      r.entityType || "",
      r.entityId || "",
      r.statusCode,
      r.operator || "",
      r.ipAddress || "",
      r.durationMs ?? "",
    ].map((v) => `"${String(v).replace(/"/g, '""')}"`).join(","));
    const csv = "﻿" + [headers.join(","), ...rows].join("\r\n");
    _downloadFile(csv, `audit_${_dateTag()}.csv`, "text/csv;charset=utf-8");
    ElMessage.success(`已导出 ${items.length} 条记录`);
  } catch {
    ElMessage.error("导出失败");
  } finally {
    exporting.value = false;
  }
}

async function confirmClear() {
  try {
    await ElMessageBox.confirm("确定清空所有操作历史？此操作不可恢复。", "清空确认", {
      type: "warning",
      confirmButtonText: "确认清空",
      cancelButtonText: "取消",
      confirmButtonClass: "el-button--danger",
    });
    await clearAuditLogs();
    ElMessage.success("操作历史已清空");
    load(1);
  } catch (e) {
    if (e !== "cancel") ElMessage.error(e?.message || "清空失败");
  }
}

onMounted(() => load(1));
</script>

<style scoped>
:deep(.row-highlight-task td) {
  background-color: #f0fdf4 !important;
}
</style>
