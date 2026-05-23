<template>
  <div class="copy-gen-agent-manager">
    <el-row :gutter="16">
      <!-- Left: list -->
      <el-col :xs="24" :sm="10" :md="8" :lg="8" :xl="6">
        <el-card shadow="never" class="dark:!bg-gray-800 dark:!border-gray-700">
          <template #header>
            <div class="flex items-center justify-between">
              <span class="font-semibold dark:text-gray-100">
                {{ t("copyGen.agent.listTitle") }}
                <span class="text-xs text-gray-500 ml-2">
                  ({{ filteredAgents.length }})
                </span>
              </span>
              <el-button type="primary" size="small" @click="onCreate">
                {{ t("copyGen.agent.add") }}
              </el-button>
            </div>
          </template>

          <el-input
            v-model="search"
            :placeholder="t('copyGen.agent.searchPlaceholder')"
            clearable
            size="small"
            class="mb-2"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>

          <div
            v-if="store.loading.agents && store.agents.length === 0"
            class="text-sm text-gray-400 italic py-6 text-center"
          >
            {{ t("copyGen.common.loading") }}
          </div>
          <div
            v-else-if="filteredAgents.length === 0"
            class="text-sm text-gray-400 italic py-6 text-center"
          >
            {{ t("copyGen.agent.empty") }}
          </div>
          <div
            v-else
            class="flex flex-col gap-2"
            style="max-height: 600px; overflow-y: auto;"
          >
            <div
              v-for="a in filteredAgents"
              :key="a.id"
              class="rounded-md border p-2 cursor-pointer transition-colors"
              :class="
                selectedId === a.id
                  ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20 ring-1 ring-blue-300'
                  : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 hover:bg-gray-50 dark:hover:bg-gray-800'
              "
              @click="selectAgent(a)"
            >
              <div class="flex items-center justify-between">
                <span class="font-medium text-sm dark:text-gray-100">
                  {{ a.name }}
                </span>
                <el-tag
                  v-if="a.is_active === false"
                  size="small"
                  type="info"
                  effect="plain"
                >
                  {{ t("copyGen.agent.inactive") }}
                </el-tag>
              </div>
              <div
                v-if="a.description"
                class="text-xs text-gray-500 dark:text-gray-400 mt-1 line-clamp-2"
              >
                {{ a.description }}
              </div>
              <div
                class="text-xs text-gray-400 dark:text-gray-500 mt-1 flex items-center gap-2 flex-wrap"
              >
                <span v-if="a.platform">{{ a.platform }}</span>
                <span v-if="a.industry">·</span>
                <span v-if="a.industry">{{ a.industry }}</span>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- Right: detail / create -->
      <el-col :xs="24" :sm="14" :md="16" :lg="16" :xl="18">
        <div
          v-if="!selectedAgent && !creating"
          class="rounded-xl border border-dashed border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 p-12 text-center"
        >
          <div class="text-gray-500 dark:text-gray-400">
            {{ t("copyGen.agent.selectHint") }}
          </div>
        </div>
        <AgentDetail
          v-else
          :key="creating ? 'create' : selectedAgent?.id"
          :agent="creating ? null : selectedAgent"
          :is-create="creating"
          @saved="onSaved"
          @deleted="onDeleted"
        />
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { Search } from "@element-plus/icons-vue";
import { useI18n } from "vue-i18n";
import { useCopyGenStore } from "../../store/modules/copyGen";
import AgentDetail from "./AgentDetail.vue";

const { t } = useI18n();
const store = useCopyGenStore();

const search = ref("");
const selectedId = ref(null);
const creating = ref(false);

const filteredAgents = computed(() => {
  const q = search.value.trim().toLowerCase();
  if (!q) return store.agents;
  return store.agents.filter((a) => {
    return (
      (a.name || "").toLowerCase().includes(q) ||
      (a.description || "").toLowerCase().includes(q) ||
      (a.platform || "").toLowerCase().includes(q) ||
      (a.industry || "").toLowerCase().includes(q)
    );
  });
});

const selectedAgent = computed(() => {
  if (selectedId.value == null) return null;
  return store.agents.find((a) => a.id === selectedId.value) || null;
});

function selectAgent(a) {
  creating.value = false;
  selectedId.value = a.id;
}

function onCreate() {
  creating.value = true;
  selectedId.value = null;
}

function onSaved(saved) {
  if (saved && saved.id != null) {
    creating.value = false;
    selectedId.value = saved.id;
  }
}

function onDeleted() {
  creating.value = false;
  selectedId.value = null;
}

onMounted(async () => {
  if (store.agents.length === 0) {
    try {
      await store.fetchAgents();
    } catch (e) {
      // eslint-disable-next-line no-console
      console.warn("[AgentManager] fetchAgents failed", e);
    }
  }
});
</script>
