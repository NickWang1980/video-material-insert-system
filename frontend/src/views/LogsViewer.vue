<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-bold">日志查看器</h1>
      <el-button size="small" @click="refreshAll" :loading="loadingCategories">刷新全部</el-button>
    </div>

    <el-tabs v-model="activeCategory" @tab-change="onTabChange" class="logs-tabs">
      <el-tab-pane
        v-for="cat in categories"
        :key="cat.key"
        :name="cat.key"
      >
        <template #label>
          {{ cat.label }}
          <span class="text-xs text-gray-400 ml-1">({{ cat.item_count }})</span>
        </template>

        <div class="grid grid-cols-12 gap-4" style="min-height: 600px">
          <!-- 左侧 item 列表 -->
          <div class="col-span-3 border border-gray-200 rounded-lg overflow-hidden flex flex-col">
            <div class="px-3 py-2 border-b border-gray-100 bg-gray-50 flex items-center justify-between">
              <span class="text-sm font-medium">日志条目</span>
              <el-button size="small" text @click="loadItems(cat.key)" :loading="loadingItems">刷新</el-button>
            </div>
            <div class="flex-1 overflow-auto" style="max-height: 700px">
              <div
                v-for="item in items"
                :key="item.id"
                class="px-3 py-2 border-b border-gray-100 cursor-pointer hover:bg-gray-50 transition-colors"
                :class="selectedItemId === item.id ? 'bg-blue-50 border-l-2 border-l-blue-500' : ''"
                @click="selectItem(item)"
              >
                <div class="text-xs font-mono break-all">{{ item.name }}</div>
                <div class="text-xs text-gray-500 mt-1">
                  {{ formatSize(item.size_bytes) }} · {{ formatTime(item.mtime_ts) }}
                </div>
              </div>
              <div v-if="!items.length && !loadingItems" class="text-center text-xs text-gray-400 py-6">
                暂无日志
              </div>
            </div>
          </div>

          <!-- 右侧内容 -->
          <div class="col-span-9 border border-gray-200 rounded-lg overflow-hidden flex flex-col">
            <div class="px-3 py-2 border-b border-gray-100 bg-gray-50 flex items-center justify-between flex-wrap gap-2">
              <div class="flex items-center gap-3 text-sm">
                <span v-if="selected" class="font-medium">{{ selected.name }}</span>
                <span v-if="selected" class="text-xs text-gray-500">
                  {{ formatSize(selected.size_bytes || 0) }}
                  · 显示末尾 {{ tailLines }} 行
                  <el-tag v-if="content?.is_truncated" type="warning" size="small" class="ml-1">已截断</el-tag>
                </span>
                <span v-else class="text-gray-400">请从左侧选择一个日志</span>
              </div>
              <div class="flex items-center gap-2">
                <el-input-number
                  v-model="tailLines"
                  :min="100"
                  :max="100000"
                  :step="500"
                  size="small"
                  controls-position="right"
                  style="width: 130px"
                  :disabled="!selected"
                  @change="reloadContent"
                />
                <el-checkbox v-model="autoRefresh" :disabled="!selected" size="small">自动刷新 2s</el-checkbox>
                <el-button size="small" :disabled="!selected" :loading="loadingContent" @click="reloadContent">
                  刷新
                </el-button>
                <el-button size="small" :disabled="!selected || !content?.content" @click="copyContent">
                  复制
                </el-button>
                <el-button
                  size="small"
                  type="primary"
                  :disabled="!selected"
                  tag="a"
                  @click="downloadFull"
                >下载完整</el-button>
              </div>
            </div>
            <div class="flex-1 overflow-auto bg-gray-900 text-gray-100" style="max-height: 700px">
              <pre
                ref="contentRef"
                class="text-xs font-mono p-3 m-0 whitespace-pre-wrap break-all"
              >{{ content?.content || (selected ? '（空）' : '') }}</pre>
            </div>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import * as logsApi from "../api/logs";

const categories = ref([]);
const loadingCategories = ref(false);
const activeCategory = ref("");
const items = ref([]);
const loadingItems = ref(false);
const selectedItemId = ref("");
const content = ref(null);
const loadingContent = ref(false);
const tailLines = ref(1000);
const autoRefresh = ref(false);
const contentRef = ref(null);

let refreshTimer = null;

const selected = computed(() =>
  items.value.find((i) => i.id === selectedItemId.value) || null
);

onMounted(async () => {
  await refreshAll();
});

onUnmounted(() => {
  stopAutoRefresh();
});

watch(autoRefresh, (val) => {
  if (val) startAutoRefresh();
  else stopAutoRefresh();
});

async function refreshAll() {
  loadingCategories.value = true;
  try {
    categories.value = await logsApi.getLogCategories();
    if (!activeCategory.value && categories.value.length) {
      activeCategory.value = categories.value[0].key;
      await loadItems(activeCategory.value);
    }
  } catch (e) {
    ElMessage.error(`加载类别失败：${e?.message || e}`);
  } finally {
    loadingCategories.value = false;
  }
}

async function onTabChange(key) {
  selectedItemId.value = "";
  content.value = null;
  await loadItems(key);
}

async function loadItems(category) {
  loadingItems.value = true;
  try {
    items.value = await logsApi.getLogItems(category);
  } catch (e) {
    ElMessage.error(`加载日志列表失败：${e?.message || e}`);
    items.value = [];
  } finally {
    loadingItems.value = false;
  }
}

async function selectItem(item) {
  selectedItemId.value = item.id;
  await reloadContent();
  if (autoRefresh.value) startAutoRefresh();
}

async function reloadContent() {
  if (!selected.value) {
    content.value = null;
    return;
  }
  loadingContent.value = true;
  try {
    content.value = await logsApi.tailLog(
      activeCategory.value,
      selected.value.id,
      tailLines.value
    );
    await nextTick();
    // 自动滚到底（tail 视图常用）
    if (contentRef.value) {
      contentRef.value.parentElement.scrollTop = contentRef.value.parentElement.scrollHeight;
    }
  } catch (e) {
    ElMessage.error(`加载内容失败：${e?.message || e}`);
  } finally {
    loadingContent.value = false;
  }
}

function startAutoRefresh() {
  stopAutoRefresh();
  refreshTimer = setInterval(reloadContent, 2000);
}
function stopAutoRefresh() {
  if (refreshTimer) {
    clearInterval(refreshTimer);
    refreshTimer = null;
  }
}

async function copyContent() {
  if (!content.value?.content) return;
  try {
    await navigator.clipboard.writeText(content.value.content);
    ElMessage.success("已复制到剪贴板");
  } catch (e) {
    ElMessage.error(`复制失败：${e?.message || e}`);
  }
}

function downloadFull() {
  if (!selected.value) return;
  const url = logsApi.logDownloadUrl(activeCategory.value, selected.value.id);
  // 用临时 a 标签触发下载（带 ?token= 兼容直链鉴权）
  const a = document.createElement("a");
  a.href = url;
  a.download = selected.value.name;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

function formatSize(bytes) {
  if (!bytes) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function formatTime(ts) {
  if (!ts) return "";
  const d = new Date(ts * 1000);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}
</script>

<style scoped>
.logs-tabs :deep(.el-tabs__content) {
  overflow: visible;
}
</style>
