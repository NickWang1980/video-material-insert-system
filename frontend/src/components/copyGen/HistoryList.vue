<template>
  <div class="copy-gen-history-list">
    <el-tabs v-model="activeTab" @tab-change="onTabChange">
      <!-- Local history -->
      <el-tab-pane :label="t('copyGen.history.localTab')" name="local">
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs text-gray-500 dark:text-gray-400">
            {{ t("copyGen.history.localCount", { count: store.history.length }) }}
          </span>
          <el-popconfirm
            :title="t('copyGen.history.confirmClear')"
            :confirm-button-text="t('copyGen.common.confirm')"
            :cancel-button-text="t('copyGen.common.cancel')"
            @confirm="onClearLocal"
          >
            <template #reference>
              <el-button
                size="small"
                text
                type="danger"
                :disabled="store.history.length === 0"
              >
                {{ t("copyGen.history.clear") }}
              </el-button>
            </template>
          </el-popconfirm>
        </div>
        <div
          v-if="store.history.length === 0"
          class="text-sm text-gray-400 italic py-6 text-center"
        >
          {{ t("copyGen.history.empty") }}
        </div>
        <div
          v-else
          class="flex flex-col gap-2"
          style="max-height: 480px; overflow-y: auto;"
        >
          <div
            v-for="(item, idx) in store.history"
            :key="`${item.ts}-${idx}`"
            class="rounded-md border border-gray-200 dark:border-gray-700 p-2 bg-white dark:bg-gray-900 hover:bg-gray-50 dark:hover:bg-gray-800"
          >
            <div class="text-sm text-gray-800 dark:text-gray-200 break-words">
              {{ truncate(item?.payload?.topic, 60) }}
            </div>
            <div
              class="text-xs text-gray-500 dark:text-gray-400 flex flex-wrap gap-x-3 gap-y-1 mt-1"
            >
              <span v-if="item?.payload?.platform">
                {{ item.payload.platform }}
              </span>
              <span v-if="item?.mode">
                {{ item.mode === "agent" ? t("copyGen.history.modeAgent") : t("copyGen.history.modeQuick") }}
              </span>
              <span v-if="versionsCount(item) > 0">
                {{ t("copyGen.history.versions", { count: versionsCount(item) }) }}
              </span>
            </div>
            <div class="text-xs text-gray-400 mt-1">
              {{ formatTime(item.ts) }}
            </div>
            <div class="flex items-center gap-2 mt-1">
              <el-button
                size="small"
                text
                type="primary"
                @click="emit('reuse', item)"
              >
                {{ t("copyGen.history.reuse") }}
              </el-button>
              <el-button
                size="small"
                text
                type="danger"
                @click="onDeleteLocal(idx)"
              >
                {{ t("copyGen.history.delete") }}
              </el-button>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- Server history -->
      <el-tab-pane :label="t('copyGen.history.serverTab')" name="server">
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs text-gray-500 dark:text-gray-400">
            {{ t("copyGen.history.serverTotal", { total: store.serverHistory.total }) }}
          </span>
          <el-button size="small" text @click="loadServerHistory">
            {{ t("copyGen.common.refresh") }}
          </el-button>
        </div>
        <div
          v-if="store.loading.history && store.serverHistory.items.length === 0"
          class="text-sm text-gray-400 italic py-6 text-center"
        >
          {{ t("copyGen.common.loading") }}
        </div>
        <div
          v-else-if="store.serverHistory.items.length === 0"
          class="text-sm text-gray-400 italic py-6 text-center"
        >
          {{ t("copyGen.history.empty") }}
        </div>
        <div
          v-else
          class="flex flex-col gap-2"
          style="max-height: 480px; overflow-y: auto;"
        >
          <div
            v-for="item in store.serverHistory.items"
            :key="item.id"
            class="rounded-md border border-gray-200 dark:border-gray-700 p-2 bg-white dark:bg-gray-900"
          >
            <div class="text-sm text-gray-800 dark:text-gray-200 break-words">
              {{ truncate(serverTopic(item), 60) }}
            </div>
            <div
              class="text-xs text-gray-500 dark:text-gray-400 flex flex-wrap gap-x-3 gap-y-1 mt-1"
            >
              <span v-if="serverPlatform(item)">
                {{ serverPlatform(item) }}
              </span>
              <span v-if="serverVersionsCount(item) > 0">
                {{
                  t("copyGen.history.versions", {
                    count: serverVersionsCount(item),
                  })
                }}
              </span>
            </div>
            <div class="text-xs text-gray-400 mt-1">
              {{ formatTime(item.created_at) }}
            </div>
            <div class="flex items-center gap-2 mt-1">
              <el-button
                size="small"
                text
                type="primary"
                @click="emit('reuse', { payload: item.payload, result: item.results })"
              >
                {{ t("copyGen.history.reuse") }}
              </el-button>
              <el-popconfirm
                :title="t('copyGen.history.confirmDelete')"
                :confirm-button-text="t('copyGen.common.confirm')"
                :cancel-button-text="t('copyGen.common.cancel')"
                @confirm="onDeleteServer(item.id)"
              >
                <template #reference>
                  <el-button size="small" text type="danger">
                    {{ t("copyGen.history.delete") }}
                  </el-button>
                </template>
              </el-popconfirm>
            </div>
          </div>
        </div>
        <div
          v-if="store.serverHistory.total > pageSize"
          class="flex items-center justify-center mt-3"
        >
          <el-pagination
            v-model:current-page="currentPage"
            :page-size="pageSize"
            :total="store.serverHistory.total"
            layout="prev, pager, next"
            small
            background
            @current-change="onPageChange"
          />
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { ElMessage } from "element-plus";
import { useI18n } from "vue-i18n";
import { useCopyGenStore } from "../../store/modules/copyGen";

const emit = defineEmits(["reuse"]);
const { t } = useI18n();
const store = useCopyGenStore();

const activeTab = ref("local");
const currentPage = ref(1);
const pageSize = 20;

function truncate(text, maxLen) {
  if (!text) return t("copyGen.history.emptyTopic");
  const s = String(text);
  return s.length > maxLen ? `${s.slice(0, maxLen)}…` : s;
}

function formatTime(ts) {
  if (!ts) return "";
  try {
    const d = typeof ts === "string" ? new Date(ts) : new Date(Number(ts));
    return d.toLocaleString();
  } catch {
    return String(ts);
  }
}

function versionsCount(item) {
  const r = item?.result;
  if (!r) return 0;
  return Array.isArray(r.versions) ? r.versions.length : 0;
}

function serverTopic(item) {
  return item?.payload?.topic || item?.topic || "";
}

function serverPlatform(item) {
  return item?.payload?.platform || item?.platform || "";
}

function serverVersionsCount(item) {
  const r = item?.results;
  if (!r) return 0;
  return Array.isArray(r.versions) ? r.versions.length : 0;
}

async function loadServerHistory() {
  try {
    await store.fetchServerHistory({
      limit: pageSize,
      offset: (currentPage.value - 1) * pageSize,
    });
  } catch (e) {
    ElMessage.error(
      t("copyGen.common.errorMsg", { msg: e?.message || String(e) })
    );
  }
}

async function onTabChange(name) {
  if (name === "server" && store.serverHistory.items.length === 0) {
    await loadServerHistory();
  }
}

function onPageChange(p) {
  currentPage.value = p;
  loadServerHistory();
}

function onClearLocal() {
  store.clearLocalHistory();
  ElMessage.success(t("copyGen.history.cleared"));
}

function onDeleteLocal(idx) {
  store.deleteLocalHistoryAt(idx);
}

async function onDeleteServer(id) {
  try {
    await store.deleteServerHistory(id);
    ElMessage.success(t("copyGen.history.deleted"));
  } catch (e) {
    ElMessage.error(
      t("copyGen.common.errorMsg", { msg: e?.message || String(e) })
    );
  }
}
</script>
