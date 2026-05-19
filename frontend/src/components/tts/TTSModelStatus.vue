<template>
  <el-card class="tts-model-status" shadow="never">
    <template #header>
      <div class="flex items-center justify-between">
        <span class="font-medium">{{ t("tts.modelStatus.title") }}</span>
        <el-tag :type="phaseTagType()" size="small">
          {{ t(`tts.modelStatus.phase.${store.status.phase || "idle"}`) }}
        </el-tag>
      </div>
    </template>

    <div class="space-y-3">
      <el-progress
        v-if="store.status.phase === 'loading'"
        :percentage="Number(store.status.percent) || 0"
        :status="phaseToProgressStatus()"
      />

      <div
        v-if="store.status.detail || store.status.message"
        class="text-sm text-gray-500"
      >
        {{ store.status.detail || store.status.message }}
      </div>

      <div
        v-if="Number(store.status.elapsed_sec) > 0"
        class="text-xs text-gray-400"
      >
        {{
          t("tts.modelStatus.elapsed", { seconds: store.status.elapsed_sec })
        }}
      </div>

      <el-alert
        v-if="store.status.error"
        type="error"
        :title="String(store.status.error)"
        :closable="false"
        show-icon
      />

      <div>
        <div class="text-xs text-gray-500 mb-1">
          {{ t("tts.modelStatus.loadedModels") }}
        </div>
        <div class="flex flex-wrap gap-2">
          <template v-if="loadedModels.length > 0">
            <el-tag
              v-for="m in loadedModels"
              :key="m"
              type="success"
              size="small"
            >
              {{ m }}
            </el-tag>
          </template>
          <span v-else class="text-sm text-gray-400">
            {{ t("tts.modelStatus.noneLoaded") }}
          </span>
        </div>
      </div>

      <div class="flex flex-wrap gap-2 pt-1">
        <el-button
          type="primary"
          :loading="store.isLoading"
          :disabled="store.status.base_loaded || store.isLoading"
          @click="onLoadBase"
        >
          {{ t("tts.modelStatus.loadBase") }}
          <span class="ml-1 text-xs opacity-80">
            ({{ t("tts.modelStatus.modelSizeBase") }})
          </span>
        </el-button>
        <el-button
          type="primary"
          plain
          :loading="store.isLoading"
          :disabled="store.status.custom_loaded || store.isLoading"
          @click="onLoadCustom"
        >
          {{ t("tts.modelStatus.loadCustom") }}
          <span class="ml-1 text-xs opacity-80">
            ({{ t("tts.modelStatus.modelSizeCustom") }})
          </span>
        </el-button>
        <el-button
          type="danger"
          plain
          :disabled="loadedModels.length === 0 || store.isLoading"
          @click="onUnload"
        >
          {{ t("tts.modelStatus.unloadAll") }}
        </el-button>
      </div>

      <div class="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
        ⓘ {{ t("tts.modelStatus.memoryNote") }}
      </div>
    </div>
  </el-card>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount } from "vue";
import { ElMessage } from "element-plus";
import { useI18n } from "vue-i18n";
import { useTTSStore } from "../../store/modules/tts";

const store = useTTSStore();
const { t } = useI18n();

const loadedModels = computed(() =>
  Array.isArray(store.status.loaded_models) ? store.status.loaded_models : []
);

onMounted(async () => {
  try {
    await store.fetchStatus();
  } catch {
    // 忽略首次失败 — 轮询会继续重试
  }
  // 始终轮询，让 phase / loaded_models 实时更新；2s 间隔
  store.startPolling(2000);
});

// 卸载时释放本组件持有的 polling 引用计数。
// store 内部使用引用计数：只有当所有调用方都 stopPolling 后才真正 clearInterval，
// 因此即便父页面 TTSStudio 也调用了 stopPolling，这里再调一次也是安全的。
onBeforeUnmount(() => {
  store.stopPolling();
});

function phaseToProgressStatus() {
  const p = store.status.phase;
  if (p === "error") return "exception";
  if (p === "ready") return "success";
  return "";
}

function phaseTagType() {
  const p = store.status.phase;
  if (p === "ready") return "success";
  if (p === "loading") return "warning";
  if (p === "error") return "danger";
  return "info";
}

async function onLoadBase() {
  try {
    await store.loadBase();
    ElMessage.success(t("tts.modelStatus.loadTriggered"));
  } catch (e) {
    ElMessage.error(t("tts.common.error", { msg: e?.message || String(e) }));
  }
}

async function onLoadCustom() {
  try {
    await store.loadCustom();
    ElMessage.success(t("tts.modelStatus.loadTriggered"));
  } catch (e) {
    ElMessage.error(t("tts.common.error", { msg: e?.message || String(e) }));
  }
}

async function onUnload() {
  try {
    await store.unloadAll();
    ElMessage.success(t("tts.modelStatus.unloadDone"));
  } catch (e) {
    ElMessage.error(t("tts.common.error", { msg: e?.message || String(e) }));
  }
}
</script>
