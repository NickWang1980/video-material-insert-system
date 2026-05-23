<template>
  <div class="p-4 max-w-7xl mx-auto space-y-4">
    <!-- Header -->
    <div class="flex items-start justify-between gap-4">
      <div>
        <h1 class="text-2xl font-bold dark:text-gray-100">
          {{ t("copyGen.page.title") }}
        </h1>
        <div class="text-sm text-gray-500 dark:text-gray-400 mt-1">
          {{ t("copyGen.page.subtitle") }}
        </div>
      </div>
      <el-button @click="onToggleLocale">
        {{ t("copyGen.page.switchLang") }}
      </el-button>
    </div>

    <!-- Status bar: current model + agent -->
    <el-card shadow="never" class="dark:!bg-gray-800 dark:!border-gray-700">
      <div class="flex items-center gap-4 flex-wrap">
        <div class="flex items-center gap-2">
          <span class="text-xs text-gray-500 dark:text-gray-400">
            {{ t("copyGen.statusBar.model") }}
          </span>
          <el-tag
            :type="currentModel ? 'success' : 'info'"
            size="small"
            effect="plain"
            class="cursor-pointer"
            @click="activeTab = 'models'"
          >
            {{
              currentModel
                ? `${currentModel.name} (${currentModel.model_name})`
                : t("copyGen.statusBar.noModel")
            }}
          </el-tag>
        </div>
        <div class="flex items-center gap-2">
          <span class="text-xs text-gray-500 dark:text-gray-400">
            {{ t("copyGen.statusBar.agent") }}
          </span>
          <el-tag
            :type="currentAgent ? 'success' : 'info'"
            size="small"
            effect="plain"
            class="cursor-pointer"
            @click="activeTab = 'agents'"
          >
            {{
              currentAgent ? currentAgent.name : t("copyGen.statusBar.noAgent")
            }}
          </el-tag>
        </div>
        <div class="flex-1" />
        <el-button size="small" text @click="onRefresh">
          {{ t("copyGen.common.refresh") }}
        </el-button>
      </div>
    </el-card>

    <!-- Main tabs -->
    <el-card shadow="never" class="dark:!bg-gray-800 dark:!border-gray-700">
      <el-tabs v-model="activeTab">
        <el-tab-pane :label="t('copyGen.tabs.quickGen')" name="quick">
          <QuickGenerator @goto-tab="onGotoTab" />
        </el-tab-pane>
        <el-tab-pane :label="t('copyGen.tabs.agents')" name="agents">
          <AgentManager />
        </el-tab-pane>
        <el-tab-pane :label="t('copyGen.tabs.models')" name="models">
          <ModelConfigManager />
        </el-tab-pane>
        <el-tab-pane :label="t('copyGen.tabs.history')" name="history">
          <HistoryList @reuse="onReuseHistory" />
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from "vue";
import { ElMessage } from "element-plus";
import { useI18n } from "vue-i18n";
import { toggleLocale } from "../locale";
import { useCopyGenStore } from "../store/modules/copyGen";

import QuickGenerator from "../components/copyGen/QuickGenerator.vue";
import AgentManager from "../components/copyGen/AgentManager.vue";
import ModelConfigManager from "../components/copyGen/ModelConfigManager.vue";
import HistoryList from "../components/copyGen/HistoryList.vue";

const { t } = useI18n();
const store = useCopyGenStore();

const activeTab = ref("quick");

const currentModel = computed(() => store.currentModelConfig);
const currentAgent = computed(() => store.currentAgent);

function onToggleLocale() {
  toggleLocale();
}

function onGotoTab(name) {
  if (typeof name === "string") {
    activeTab.value = name;
  }
}

function onReuseHistory(item) {
  const p = item?.payload;
  if (!p) return;
  // Switch to quick gen tab. The QuickGenerator's own HistoryList also fires reuse,
  // but reuse from the history tab needs to land in the quick generator form too —
  // for now, the cheapest path is to switch tab + flash a hint. The quick gen
  // form rebinds on currentAgentId / currentModelConfigId already.
  if (p.model_config_id != null) {
    store.setCurrentModelConfigId(p.model_config_id);
  }
  if (item.agent_id != null) {
    store.setCurrentAgentId(item.agent_id);
  }
  activeTab.value = "quick";
  ElMessage.info(t("copyGen.history.switchedToQuick"));
}

async function onRefresh() {
  try {
    await Promise.all([
      store.fetchEnums(true),
      store.fetchModelConfigs(),
      store.fetchAgents(),
    ]);
    ElMessage.success(t("copyGen.common.refreshed"));
  } catch (e) {
    ElMessage.error(
      t("copyGen.common.errorMsg", { msg: e?.message || String(e) })
    );
  }
}

// Auto-pick first model when list loads (mirrors QuickGenerator behavior so
// the top status bar reflects current selection immediately).
watch(
  () => store.modelConfigs.length,
  (n) => {
    if (n > 0 && store.currentModelConfigId == null) {
      store.setCurrentModelConfigId(store.modelConfigs[0].id);
    }
  }
);

onMounted(async () => {
  // Fire all bootstrapping in parallel; individual failures are swallowed so the
  // page still renders (errors will surface again when user hits Refresh / a CRUD).
  await Promise.allSettled([
    store.fetchEnums().catch((e) => {
      // eslint-disable-next-line no-console
      console.warn("[CopyGen] fetchEnums failed:", e);
    }),
    store.fetchModelConfigs().catch((e) => {
      // eslint-disable-next-line no-console
      console.warn("[CopyGen] fetchModelConfigs failed:", e);
    }),
    store.fetchAgents().catch((e) => {
      // eslint-disable-next-line no-console
      console.warn("[CopyGen] fetchAgents failed:", e);
    }),
  ]);
});
</script>

<style scoped>
:deep(.el-tabs__nav-wrap::after) {
  background-color: var(--el-border-color-lighter);
}
</style>
