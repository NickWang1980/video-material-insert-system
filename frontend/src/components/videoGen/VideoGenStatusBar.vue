<template>
  <div
    class="px-4 py-3 rounded-lg border flex items-center justify-between gap-3"
    :class="bannerClass"
  >
    <div class="flex items-center gap-3 min-w-0">
      <span class="inline-flex items-center justify-center w-6 h-6 rounded-full" :class="dotClass">
        <span class="text-white text-xs">●</span>
      </span>
      <div class="min-w-0">
        <div class="text-sm font-semibold truncate">{{ titleText }}</div>
        <div class="text-xs text-gray-500 truncate">{{ subtitleText }}</div>
      </div>
    </div>
    <div class="flex items-center gap-2">
      <el-button
        v-if="showStartButton"
        size="small"
        type="primary"
        :loading="starting"
        @click="onStart"
      >
        启动 heygem
      </el-button>
      <el-button size="small" :loading="loading" @click="$emit('refresh')">刷新</el-button>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";
import { ElMessage } from "element-plus";
import { useVideoGenStore } from "../../store/modules/videoGen";

const props = defineProps({
  health: { type: Object, required: true },
  loading: { type: Boolean, default: false },
});
defineEmits(["refresh"]);

const store = useVideoGenStore();
const starting = ref(false);

// 仅在「manual」显存策略 + heygem 已启用但当前不可达时显示。
// 其他策略（tts_unload / cuda_isolate）是 Phase-2 才生效，这里默认不让用户绕过。
const showStartButton = computed(
  () =>
    store.vramStrategy === "manual" &&
    props.health?.enabled &&
    !props.health?.reachable
);

async function onStart() {
  starting.value = true;
  try {
    const r = await store.startSidecarAndWait();
    if (r.already_running) {
      ElMessage.info("heygem 已经在跑，直接刷新即可");
    } else if (r.started) {
      ElMessage.success(
        `已在新 cmd 窗口启动 heygem (pid=${r.pid})。首次约 30-90s，请耐心等状态条变绿。`
      );
    } else {
      ElMessage.warning(r.detail || "启动请求已发出，但服务端没确认 started");
    }
  } catch (e) {
    ElMessage.error(`启动失败：${e?.response?.data?.detail || e?.message || e}`);
  } finally {
    starting.value = false;
  }
}

const isHealthy = computed(
  () => props.health?.enabled && props.health?.reachable && props.health?.heygem_ready === true
);

const titleText = computed(() => {
  if (!props.health?.enabled) return "heygem 已通过 .env 禁用 (HEYGEM_ENABLED=0)";
  if (!props.health?.reachable) return "heygem 服务未连接";
  if (props.health?.heygem_ready === false) return "heygem 正在初始化（首次约 30s）";
  return "heygem 已就绪";
});

const subtitleText = computed(() => {
  const parts = [];
  if (props.health?.base_url) parts.push(`endpoint: ${props.health.base_url}`);
  if (props.health?.heygem_gpu) parts.push(`GPU: ${props.health.heygem_gpu}`);
  if (props.health?.detail) parts.push(props.health.detail);
  return parts.length ? parts.join(" · ") : "请运行 vendor/heygem/start_api.bat";
});

const bannerClass = computed(() => {
  if (isHealthy.value) return "border-green-300 bg-green-50";
  if (!props.health?.enabled) return "border-gray-300 bg-gray-50";
  return "border-red-300 bg-red-50";
});

const dotClass = computed(() => {
  if (isHealthy.value) return "bg-green-500";
  if (!props.health?.enabled) return "bg-gray-400";
  return "bg-red-500";
});
</script>
