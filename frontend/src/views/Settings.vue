<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <el-button @click="load">刷新</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </div>
    </div>

    <div class="p-6 rounded-xl border border-gray-200 shadow-card space-y-6" v-loading="loading">
      <div>
        <div class="text-lg font-bold mb-4">视频输出设置</div>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <div class="text-sm font-medium mb-2">输出格式</div>
            <el-select v-model="form.output_format" class="w-full">
              <el-option label="MP4" value="MP4" />
              <el-option label="MOV" value="MOV" />
            </el-select>
          </div>
          <div>
            <div class="text-sm font-medium mb-2">分辨率</div>
            <el-select v-model="form.resolution" class="w-full">
              <el-option label="720P" value="720P" />
              <el-option label="1080P" value="1080P" />
              <el-option label="4K" value="4K" />
            </el-select>
          </div>
          <div>
            <div class="text-sm font-medium mb-2">视频码率(kbps)</div>
            <el-input-number v-model="form.video_bitrate_kbps" :min="500" :step="500" class="w-full" />
          </div>
        </div>
      </div>

      <div>
        <div class="text-lg font-bold mb-4">视频编码器（GPU 加速）</div>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <div class="text-sm font-medium mb-2">编码器</div>
            <el-select v-model="form.video_encoder_mode" class="w-full">
              <el-option label="自动检测（推荐）" value="auto" />
              <el-option label="CPU（libx264）" value="cpu" />
              <el-option label="CUDA / NVENC（NVIDIA）" value="cuda" />
              <el-option label="Intel QSV（Quick Sync）" value="qsv" />
              <el-option label="AMD AMF" value="amf" />
            </el-select>
            <div class="text-xs text-gray-500 mt-1">硬件不支持时自动回退到 CPU</div>
          </div>
        </div>
      </div>

      <div>
        <div class="text-lg font-bold mb-4">字幕解析与ASR设置</div>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <div class="text-sm font-medium mb-2">字幕编码</div>
            <el-input v-model="form.subtitle_encoding" placeholder="utf-8 / gbk ..." />
          </div>
          <div>
            <div class="text-sm font-medium mb-2">时间偏移(秒)</div>
            <el-input-number v-model="form.subtitle_time_offset_seconds" :step="0.1" class="w-full" />
          </div>
          <div>
            <div class="text-sm font-medium mb-2">ASR 模型</div>
            <el-select v-model="form.asr_model" class="w-full">
              <el-option label="large-v3-turbo（首选，95% 场景最佳）" value="large-v3-turbo" />
              <el-option label="large-v3（最高精度）" value="large-v3" />
              <el-option label="medium（不推荐用于 50 系显卡）" value="medium" />
              <el-option label="small（不推荐用于 50 系显卡）" value="small" />
            </el-select>
          </div>
          <div>
            <div class="text-sm font-medium mb-2">ASR 精度</div>
            <el-select v-model="form.asr_compute_type" class="w-full">
              <el-option label="自动（推荐）" value="auto" />
              <el-option label="int8（CPU 专用，无显卡时最快）" value="int8" />
              <el-option label="float16（GPU 平衡，默认最佳）" value="float16" />
              <el-option label="float32（最高精度，慢）" value="float32" />
            </el-select>
          </div>
        </div>
      </div>
    </div>

    <!-- ── FFmpeg 工具管理 ─────────────────────────────────────────── -->
    <div class="p-6 rounded-xl border border-gray-200 shadow-card">
      <div class="flex items-center justify-between mb-4">
        <div class="text-lg font-bold">FFmpeg 工具管理</div>
        <el-button size="small" @click="loadFfmpeg" :loading="ffmpegLoading">刷新</el-button>
      </div>
      <div v-if="ffmpegInfo" class="space-y-4">
        <!-- ffmpeg 主体 -->
        <div class="space-y-2 p-4 rounded-lg border border-gray-100 bg-gray-50">
          <div class="flex items-center gap-2">
            <span class="font-semibold">ffmpeg</span>
            <el-tag v-if="ffmpegInfo.ffmpeg.ok" type="success" size="small">{{ ffmpegInfo.ffmpeg.version || "OK" }}</el-tag>
            <el-tag v-else type="danger" size="small">不可用</el-tag>
            <el-tag v-if="ffmpegInfo.encoder_active" size="small" effect="plain">当前激活：{{ ffmpegInfo.encoder_active }}</el-tag>
          </div>
          <div class="text-xs text-gray-600">
            <div><span class="text-gray-500">配置（.env）：</span><code class="font-mono">{{ ffmpegInfo.ffmpeg.configured_path }}</code></div>
            <div v-if="ffmpegInfo.ffmpeg.resolved_path && ffmpegInfo.ffmpeg.resolved_path !== ffmpegInfo.ffmpeg.configured_path">
              <span class="text-gray-500">实际位置：</span><code class="font-mono break-all">{{ ffmpegInfo.ffmpeg.resolved_path }}</code>
            </div>
            <div v-if="ffmpegInfo.ffmpeg.size_bytes > 0">
              <span class="text-gray-500">大小：</span>{{ formatSize(ffmpegInfo.ffmpeg.size_bytes) }}
            </div>
            <div v-if="ffmpegInfo.ffmpeg.error" class="text-red-600 mt-1">
              错误：{{ ffmpegInfo.ffmpeg.error }}
            </div>
          </div>
          <div v-if="ffmpegInfo.hw_encoders.length" class="text-xs">
            <span class="text-gray-500">硬件编码器：</span>
            <el-tag
              v-for="enc in ffmpegInfo.hw_encoders"
              :key="enc"
              size="small"
              class="mr-1"
              :type="encoderTagType(enc)"
            >{{ enc }}</el-tag>
          </div>
          <div v-else-if="ffmpegInfo.ffmpeg.ok" class="text-xs text-amber-600">
            未检测到硬件编码器（仅可用 CPU libx264）
          </div>
          <details v-if="ffmpegInfo.ffmpeg_configuration" class="text-xs">
            <summary class="cursor-pointer text-gray-500 hover:text-gray-700">编译特性（点击展开）</summary>
            <div class="mt-2 p-2 bg-white border border-gray-200 rounded font-mono text-[10px] break-all whitespace-pre-wrap">
              {{ ffmpegInfo.ffmpeg_configuration }}
            </div>
          </details>
        </div>

        <!-- ffprobe -->
        <div class="space-y-2 p-4 rounded-lg border border-gray-100 bg-gray-50">
          <div class="flex items-center gap-2">
            <span class="font-semibold">ffprobe</span>
            <el-tag v-if="ffmpegInfo.ffprobe.ok" type="success" size="small">{{ ffmpegInfo.ffprobe.version || "OK" }}</el-tag>
            <el-tag v-else type="danger" size="small">不可用</el-tag>
          </div>
          <div class="text-xs text-gray-600">
            <div><span class="text-gray-500">配置（.env）：</span><code class="font-mono">{{ ffmpegInfo.ffprobe.configured_path }}</code></div>
            <div v-if="ffmpegInfo.ffprobe.resolved_path && ffmpegInfo.ffprobe.resolved_path !== ffmpegInfo.ffprobe.configured_path">
              <span class="text-gray-500">实际位置：</span><code class="font-mono break-all">{{ ffmpegInfo.ffprobe.resolved_path }}</code>
            </div>
            <div v-if="ffmpegInfo.ffprobe.size_bytes > 0">
              <span class="text-gray-500">大小：</span>{{ formatSize(ffmpegInfo.ffprobe.size_bytes) }}
            </div>
            <div v-if="ffmpegInfo.ffprobe.error" class="text-red-600 mt-1">
              错误：{{ ffmpegInfo.ffprobe.error }}
            </div>
          </div>
        </div>

        <div class="text-xs text-gray-500">
          路径来源：<code class="font-mono">backend/.env</code> 中的 <code>FFMPEG_BIN</code> / <code>FFPROBE_BIN</code>。修改路径需编辑该文件后重启后端。
        </div>
      </div>
      <div v-else-if="!ffmpegLoading" class="text-sm text-gray-500">
        点击"刷新"加载 FFmpeg 工具信息
      </div>
    </div>

    <!-- ── 缓存清理 ─────────────────────────────────────────────────── -->
    <div class="p-6 rounded-xl border border-gray-200 shadow-card">
      <div class="flex items-center justify-between mb-4">
        <div class="text-lg font-bold">缓存清理</div>
        <div class="flex items-center gap-2">
          <el-button size="small" @click="loadCache" :loading="cacheLoading">刷新</el-button>
          <el-button
            size="small"
            type="primary"
            :disabled="!selectedCacheKeys.length"
            :loading="clearing"
            @click="confirmClearCache"
          >
            清理选中（{{ formatSize(selectedCacheBytes) }}）
          </el-button>
        </div>
      </div>
      <el-table
        :data="cacheCategories"
        v-loading="cacheLoading"
        @selection-change="onCacheSelect"
        ref="cacheTableRef"
        style="width: 100%"
      >
        <el-table-column type="selection" width="48" :selectable="(row) => row.size_bytes > 0" />
        <el-table-column label="类别" min-width="180">
          <template #default="{ row }">
            <div class="flex items-center gap-2">
              <span class="font-medium">{{ row.label }}</span>
              <el-tag v-if="row.safe" type="success" size="small">安全</el-tag>
              <el-tag v-else type="warning" size="small">需确认</el-tag>
            </div>
            <div class="text-xs text-gray-500 mt-1">{{ row.description }}</div>
          </template>
        </el-table-column>
        <el-table-column label="路径" min-width="320">
          <template #default="{ row }">
            <div v-if="row.paths.length" class="space-y-0.5">
              <div
                v-for="p in row.paths"
                :key="p"
                class="text-xs font-mono break-all text-gray-600"
              >
                {{ p }}
              </div>
            </div>
            <span v-else class="text-xs text-gray-400">（无）</span>
          </template>
        </el-table-column>
        <el-table-column label="文件数" width="90" align="right">
          <template #default="{ row }">
            <span class="text-sm">{{ row.file_count }}</span>
          </template>
        </el-table-column>
        <el-table-column label="占用" width="120" align="right">
          <template #default="{ row }">
            <span class="text-sm font-mono">{{ formatSize(row.size_bytes) }}</span>
          </template>
        </el-table-column>
      </el-table>
      <div class="text-xs text-gray-500 mt-2">
        清理范围已严格审查：成品视频 / 报告 / 数据库 / 用户上传 / ASR 模型主文件均不会被触碰。
      </div>
    </div>

    <!-- ── ASR 队列 ─────────────────────────────────────────────────── -->
    <div class="p-6 rounded-xl border border-gray-200 shadow-card">
      <div class="flex items-center justify-between mb-4">
        <div>
          <div class="text-lg font-bold">ASR 队列</div>
          <div class="text-xs text-gray-500 mt-1">
            待处理 <span class="font-semibold text-gray-700">{{ asrQueue.pending_count }}</span>
            / 运行中 <span class="font-semibold text-gray-700">{{ asrQueue.running_count }}</span>
            / 总计 <span class="font-semibold text-gray-700">{{ asrQueue.total_count }}</span>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <el-button size="small" @click="loadAsrQueue" :loading="asrQueueLoading">刷新</el-button>
          <el-button
            size="small"
            type="danger"
            :disabled="asrQueue.total_count === 0"
            :loading="asrQueueClearing"
            @click="confirmClearAsrQueue"
          >清空队列</el-button>
        </div>
      </div>
      <el-table
        :data="asrQueue.items"
        v-loading="asrQueueLoading"
        empty-text="队列为空"
        style="width: 100%"
      >
        <el-table-column label="类型" width="120">
          <template #default="{ row }">
            <el-tag size="small" type="info" v-if="row.kind === 'source_video'">源视频</el-tag>
            <el-tag size="small" type="warning" v-else-if="row.kind === 'rough_cut_asset'">混剪素材</el-tag>
            <el-tag size="small" v-else>{{ row.kind }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="名称" min-width="280">
          <template #default="{ row }">
            <div class="text-sm break-all">{{ row.name }}</div>
            <div v-if="row.extra" class="text-xs text-amber-600 mt-0.5">{{ row.extra }}</div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag size="small" type="success" v-if="row.status === 'running'">运行中</el-tag>
            <el-tag size="small" type="info" v-else>等待中</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="进度" width="160">
          <template #default="{ row }">
            <progress :value="row.progress" max="100" class="w-full" />
            <div class="text-xs text-gray-500 text-right">{{ row.progress }}%</div>
          </template>
        </el-table-column>
        <el-table-column label="模型" width="140">
          <template #default="{ row }">
            <span class="text-xs font-mono">{{ row.model || "—" }}</span>
          </template>
        </el-table-column>
      </el-table>
      <div class="text-xs text-gray-500 mt-2">
        说明：清空只取消"待处理"任务并把"运行中"标记为 failed；正在运行的转写无法即刻中断（CTranslate2 不支持），但状态已改、结果不会被保留。
      </div>
    </div>

    <!-- ── FFmpeg 队列 ──────────────────────────────────────────────── -->
    <div class="p-6 rounded-xl border border-gray-200 shadow-card">
      <div class="flex items-center justify-between mb-4">
        <div>
          <div class="text-lg font-bold">FFmpeg 队列</div>
          <div class="text-xs text-gray-500 mt-1">
            待处理 <span class="font-semibold text-gray-700">{{ ffmpegQueue.pending_count }}</span>
            / 运行中 <span class="font-semibold text-gray-700">{{ ffmpegQueue.running_count }}</span>
            / 总计 <span class="font-semibold text-gray-700">{{ ffmpegQueue.total_count }}</span>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <el-button size="small" @click="loadFfmpegQueue" :loading="ffmpegQueueLoading">刷新</el-button>
          <el-button
            size="small"
            type="danger"
            :disabled="ffmpegQueue.total_count === 0"
            :loading="ffmpegQueueClearing"
            @click="confirmClearFfmpegQueue"
          >清空队列</el-button>
        </div>
      </div>
      <el-table
        :data="ffmpegQueue.items"
        v-loading="ffmpegQueueLoading"
        empty-text="队列为空"
        style="width: 100%"
      >
        <el-table-column label="类型" width="120">
          <template #default="{ row }">
            <el-tag size="small" type="info" v-if="row.kind === 'task'">素材插入</el-tag>
            <el-tag size="small" type="warning" v-else-if="row.kind === 'rough_cut'">混剪导出</el-tag>
            <el-tag size="small" v-else>{{ row.kind }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="名称" min-width="280">
          <template #default="{ row }">
            <div class="text-sm break-all">{{ row.name }}</div>
            <div v-if="row.extra" class="text-xs text-gray-500 mt-0.5">阶段：{{ row.extra }}</div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag size="small" type="success" v-if="row.status === 'processing'">处理中</el-tag>
            <el-tag size="small" type="info" v-else>等待中</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="进度" width="160">
          <template #default="{ row }">
            <progress :value="row.progress" max="100" class="w-full" />
            <div class="text-xs text-gray-500 text-right">{{ row.progress }}%</div>
          </template>
        </el-table-column>
      </el-table>
      <div class="text-xs text-gray-500 mt-2">
        说明：清空会 terminate 全部 FFmpeg 子进程并把任务/项目状态置为 stopped；可在任务列表里手动重启。
      </div>
    </div>

    <!-- ── ASR 模型管理 ─────────────────────────────────────────────── -->
    <div class="p-6 rounded-xl border border-gray-200 shadow-card">
      <div class="flex items-center justify-between mb-4">
        <div class="text-lg font-bold">ASR 模型管理</div>
        <el-button size="small" @click="loadModels" :loading="modelsLoading">刷新</el-button>
      </div>
      <el-table :data="installedModels" stripe v-loading="modelsLoading" style="width: 100%">
        <el-table-column prop="model" label="模型" width="160">
          <template #default="{ row }">
            <div class="font-medium">{{ row.model }}</div>
            <div class="text-xs text-gray-500">{{ row.repo }}</div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.installed" type="success" size="small">已就绪</el-tag>
            <el-tag v-else-if="row.local_exists" type="warning" size="small">不完整</el-tag>
            <el-tag v-else type="info" size="small">未安装</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="本地安装路径 / 大小" min-width="320">
          <template #default="{ row }">
            <div class="text-xs font-mono break-all">{{ row.local_path }}</div>
            <div class="text-xs text-gray-500 mt-1">
              {{ row.local_exists ? formatSize(row.local_size_bytes) : "尚未下载" }}
              <span v-if="row.reason" class="text-amber-600">— {{ row.reason }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="HF 缓存路径 / 大小" min-width="280">
          <template #default="{ row }">
            <template v-if="row.hf_cache_exists">
              <div class="text-xs font-mono break-all">{{ row.hf_cache_path }}</div>
              <div class="text-xs text-gray-500 mt-1">{{ formatSize(row.hf_cache_size_bytes) }}</div>
            </template>
            <span v-else class="text-xs text-gray-400">无</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" align="right">
          <template #default="{ row }">
            <el-button
              v-if="!row.installed"
              size="small"
              type="primary"
              @click="downloadModel(row)"
            >下载</el-button>
            <el-button
              v-else
              size="small"
              @click="redownloadModel(row)"
            >重新下载</el-button>
            <el-button
              v-if="row.local_exists || row.hf_cache_exists"
              size="small"
              type="danger"
              @click="confirmDeleteModel(row)"
            >删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="text-xs text-gray-500 mt-2">
        默认仅删除项目本地路径；HF 缓存如有占用，删除时会询问是否一并清理。
      </div>
    </div>

    <!-- ── 下载进度弹窗 ─────────────────────────────────────────────── -->
    <el-dialog
      v-model="installOpen"
      title="正在安装 ASR 模型"
      width="480px"
      :close-on-click-modal="false"
      :show-close="false"
    >
      <div class="space-y-3">
        <div class="text-sm">
          <span class="font-semibold">{{ installInfo.model }}</span>
          —
          <span class="text-gray-600">{{ installInfo.message }}</span>
        </div>
        <progress
          :value="installInfo.progress"
          max="100"
          class="w-full progress-breathing"
        />
        <div class="text-xs text-gray-500 text-right">
          {{ installInfo.progress }}% / {{ installInfo.total_mb }} MB
        </div>
      </div>
      <template #footer>
        <el-button
          type="danger"
          plain
          :loading="cancelling"
          @click="cancelInstall"
        >取消下载并清理</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import * as settingsApi from "../api/settings";

const loading = ref(false);
const saving = ref(false);
const installOpen = ref(false);
const cancelling = ref(false);
const currentTaskId = ref(null);

const installInfo = reactive({
  model: "",
  progress: 0,
  message: "",
  total_mb: 0,
});

const form = reactive({
  output_format: "MP4",
  resolution: "1080P",
  video_bitrate_kbps: 6000,
  subtitle_encoding: "utf-8",
  subtitle_time_offset_seconds: 0,
  asr_model: "large-v3-turbo",
  asr_compute_type: "auto",
  video_encoder_mode: "auto",
});

const installedModels = ref([]);
const modelsLoading = ref(false);
const ffmpegInfo = ref(null);
const ffmpegLoading = ref(false);

const cacheCategories = ref([]);
const cacheLoading = ref(false);
const cacheTableRef = ref(null);
const selectedCache = ref([]);
const clearing = ref(false);

const asrQueue = ref({ items: [], pending_count: 0, running_count: 0, total_count: 0 });
const asrQueueLoading = ref(false);
const asrQueueClearing = ref(false);

const ffmpegQueue = ref({ items: [], pending_count: 0, running_count: 0, total_count: 0 });
const ffmpegQueueLoading = ref(false);
const ffmpegQueueClearing = ref(false);

onMounted(async () => {
  await load();
  await Promise.all([
    loadModels(),
    loadFfmpeg(),
    loadCache(),
    loadAsrQueue(),
    loadFfmpegQueue(),
  ]);
});

async function loadAsrQueue() {
  asrQueueLoading.value = true;
  try {
    asrQueue.value = await settingsApi.getAsrQueue();
  } catch (e) {
    ElMessage.error(`加载 ASR 队列失败：${e?.message || e}`);
  } finally {
    asrQueueLoading.value = false;
  }
}

async function confirmClearAsrQueue() {
  const total = asrQueue.value.total_count;
  if (!total) return;
  try {
    await ElMessageBox.confirm(
      `共有 ${total} 个 ASR 任务（待处理 ${asrQueue.value.pending_count} / 运行中 ${asrQueue.value.running_count}）。\n\n清空后：\n· 待处理任务直接取消；\n· 运行中转写无法即刻中断（CTranslate2 限制），但状态会置为 failed、结果不保留。\n\n确认清空？`,
      "清空 ASR 队列",
      { type: "warning", confirmButtonText: "清空", cancelButtonText: "取消" }
    );
  } catch {
    return;
  }
  asrQueueClearing.value = true;
  try {
    const res = await settingsApi.clearAsrQueue();
    ElMessage.success(
      `已取消 ${res.total_cancelled} 个 ASR 任务（源视频 ${res.cancelled_source_count} / 混剪素材 ${res.cancelled_rough_cut_count}）`
    );
    await loadAsrQueue();
  } catch (e) {
    ElMessage.error(`清空失败：${e?.response?.data?.detail || e?.message || e}`);
  } finally {
    asrQueueClearing.value = false;
  }
}

async function loadFfmpegQueue() {
  ffmpegQueueLoading.value = true;
  try {
    ffmpegQueue.value = await settingsApi.getFfmpegQueue();
  } catch (e) {
    ElMessage.error(`加载 FFmpeg 队列失败：${e?.message || e}`);
  } finally {
    ffmpegQueueLoading.value = false;
  }
}

async function confirmClearFfmpegQueue() {
  const total = ffmpegQueue.value.total_count;
  if (!total) return;
  try {
    await ElMessageBox.confirm(
      `共有 ${total} 个 FFmpeg 任务（待处理 ${ffmpegQueue.value.pending_count} / 运行中 ${ffmpegQueue.value.running_count}）。\n\n清空会终止全部 FFmpeg 子进程并将任务/项目置为 stopped。\n\n确认清空？`,
      "清空 FFmpeg 队列",
      { type: "warning", confirmButtonText: "清空", cancelButtonText: "取消" }
    );
  } catch {
    return;
  }
  ffmpegQueueClearing.value = true;
  try {
    const res = await settingsApi.clearFfmpegQueue();
    ElMessage.success(
      `已停止 ${res.total_stopped} 个任务（素材插入 ${res.stopped_task_count} / 混剪导出 ${res.stopped_rough_cut_count}）`
    );
    await loadFfmpegQueue();
  } catch (e) {
    ElMessage.error(`清空失败：${e?.response?.data?.detail || e?.message || e}`);
  } finally {
    ffmpegQueueClearing.value = false;
  }
}

async function loadCache() {
  cacheLoading.value = true;
  try {
    cacheCategories.value = await settingsApi.getCacheInfo();
    // 默认勾选所有"安全"类别且大小>0
    await nextTick();
    if (cacheTableRef.value) {
      cacheCategories.value.forEach((row) => {
        if (row.safe && row.size_bytes > 0) {
          cacheTableRef.value.toggleRowSelection(row, true);
        }
      });
    }
  } catch (e) {
    ElMessage.error(`加载缓存信息失败：${e?.message || e}`);
  } finally {
    cacheLoading.value = false;
  }
}

function onCacheSelect(rows) {
  selectedCache.value = rows;
}

const selectedCacheKeys = computed(() => selectedCache.value.map((r) => r.key));
const selectedCacheBytes = computed(() =>
  selectedCache.value.reduce((sum, r) => sum + (r.size_bytes || 0), 0)
);

async function confirmClearCache() {
  if (!selectedCacheKeys.value.length) return;
  const hasUnsafe = selectedCache.value.some((r) => !r.safe);
  const msg = hasUnsafe
    ? `将清理 ${selectedCacheKeys.value.length} 项（共 ${formatSize(selectedCacheBytes.value)}），其中包含「需确认」类别。继续？`
    : `将清理 ${selectedCacheKeys.value.length} 项（共 ${formatSize(selectedCacheBytes.value)}），均为安全类别。继续？`;
  try {
    await ElMessageBox.confirm(msg, "清理缓存", {
      confirmButtonText: "立即清理",
      cancelButtonText: "取消",
      type: hasUnsafe ? "warning" : "info",
    });
  } catch (_) {
    return;
  }
  clearing.value = true;
  try {
    const result = await settingsApi.clearCache(selectedCacheKeys.value);
    const errs = Object.values(result.summary).flatMap((s) => s.errors || []);
    if (errs.length) {
      ElMessage.warning(
        `清理完成但有 ${errs.length} 个错误：${errs.slice(0, 2).join("; ")}`
      );
    } else {
      ElMessage.success(
        `已释放 ${formatSize(result.total_freed_bytes)}（${result.total_freed_files} 个文件）`
      );
    }
    await loadCache();
  } catch (e) {
    ElMessage.error(`清理失败：${e?.response?.data?.detail || e?.message}`);
  } finally {
    clearing.value = false;
  }
}

async function loadFfmpeg() {
  ffmpegLoading.value = true;
  try {
    ffmpegInfo.value = await settingsApi.getFfmpegInfo();
  } catch (e) {
    ElMessage.error(`加载 FFmpeg 信息失败：${e?.message || e}`);
  } finally {
    ffmpegLoading.value = false;
  }
}

function encoderTagType(enc) {
  if (enc === "nvenc") return "warning";
  if (enc === "qsv") return "primary";
  if (enc === "amf") return "success";
  return "info";
}

async function load() {
  loading.value = true;
  try {
    const data = await settingsApi.getSettings();
    Object.assign(form, data);
  } finally {
    loading.value = false;
  }
}

async function loadModels() {
  modelsLoading.value = true;
  try {
    installedModels.value = await settingsApi.listAsrModels();
  } finally {
    modelsLoading.value = false;
  }
}

async function save() {
  saving.value = true;
  try {
    await settingsApi.updateSettings({ ...form });
    ElMessage.success("设置已保存");

    const check = await settingsApi.checkAsrModelInstalled(form.asr_model);
    if (!check.installed) {
      const detail = check.reason ? `\n原因：${check.reason}` : "";
      try {
        await ElMessageBox.confirm(
          `ASR 模型 ${form.asr_model} 尚未安装（约 ${check.size_mb} MB）。${detail}\n\n你的选择已保存，但跑 ASR 任务前需要先下载模型。是否立即下载？`,
          "模型未安装",
          {
            confirmButtonText: "立即下载",
            cancelButtonText: "稍后下载",
            type: "warning",
            distinguishCancelAndClose: true,
          }
        );
        await runInstall(form.asr_model);
        await loadModels();
      } catch (_) {
        ElMessage.warning(
          `已保存 ${form.asr_model} 偏好。模型未安装，下次执行 ASR 任务时会失败。`
        );
      }
    }
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || err?.message || "保存失败");
  } finally {
    saving.value = false;
  }
}

async function runInstall(model) {
  installInfo.model = model;
  installInfo.progress = 0;
  installInfo.message = "启动下载...";
  installInfo.total_mb = 0;
  installOpen.value = true;
  cancelling.value = false;
  const { task_id } = await settingsApi.installAsrModel(model);
  currentTaskId.value = task_id;
  return new Promise((resolve, reject) => {
    const timer = setInterval(async () => {
      try {
        const info = await settingsApi.getAsrInstallProgress(task_id);
        Object.assign(installInfo, info);
        if (info.status === "completed") {
          clearInterval(timer);
          installOpen.value = false;
          currentTaskId.value = null;
          ElMessage.success("模型安装完成");
          resolve();
        } else if (info.status === "failed") {
          clearInterval(timer);
          installOpen.value = false;
          currentTaskId.value = null;
          ElMessage.error(`安装失败：${info.message}`);
          reject(new Error(info.message));
        } else if (info.status === "cancelled") {
          clearInterval(timer);
          installOpen.value = false;
          currentTaskId.value = null;
          ElMessage.info("已取消下载，部分文件已清理");
          resolve();
        }
      } catch (e) {
        clearInterval(timer);
        installOpen.value = false;
        currentTaskId.value = null;
        reject(e);
      }
    }, 1000);
  });
}

async function cancelInstall() {
  if (!currentTaskId.value || cancelling.value) return;
  cancelling.value = true;
  try {
    await settingsApi.cancelAsrInstall(currentTaskId.value);
    installInfo.message = "正在取消并清理...";
  } catch (e) {
    ElMessage.error(`取消请求失败：${e?.message || e}`);
  } finally {
    cancelling.value = false;
  }
}

async function downloadModel(row) {
  try {
    await runInstall(row.model);
  } catch (_) {
    /* error already shown */
  } finally {
    await loadModels();
  }
}

async function redownloadModel(row) {
  try {
    await ElMessageBox.confirm(
      `将先删除已安装的 ${row.model}（${formatSize(row.local_size_bytes)}），再重新下载。是否继续？`,
      "重新下载",
      { confirmButtonText: "继续", cancelButtonText: "取消", type: "warning" }
    );
  } catch (_) {
    return;
  }
  await settingsApi.deleteAsrModel(row.model, false);
  await downloadModel(row);
}

async function confirmDeleteModel(row) {
  let includeHf = false;
  try {
    if (row.hf_cache_exists) {
      const action = await ElMessageBox.confirm(
        `删除 ${row.model} 项目内安装（${formatSize(row.local_size_bytes)}）。\n\n该模型在 HF 缓存里也占用 ${formatSize(row.hf_cache_size_bytes)}：\n${row.hf_cache_path}\n\n是否一并清理 HF 缓存？`,
        "删除模型",
        {
          confirmButtonText: "项目内 + HF 缓存全部删除",
          cancelButtonText: "仅删项目内",
          distinguishCancelAndClose: true,
          type: "warning",
        }
      );
      if (action === "confirm") includeHf = true;
    } else {
      await ElMessageBox.confirm(
        `确定删除 ${row.model}（${formatSize(row.local_size_bytes)}）？`,
        "删除模型",
        { confirmButtonText: "删除", cancelButtonText: "取消", type: "warning" }
      );
    }
  } catch (action) {
    if (action === "close") return; // user closed dialog
    if (!row.hf_cache_exists) return; // user chose 取消 on simple dialog
    // If hf_cache_exists branch: cancel button = 仅删项目内
    includeHf = false;
  }
  try {
    await settingsApi.deleteAsrModel(row.model, includeHf);
    ElMessage.success(`已删除 ${row.model}${includeHf ? "（含 HF 缓存）" : ""}`);
    await loadModels();
  } catch (e) {
    ElMessage.error(`删除失败：${e?.response?.data?.detail || e?.message}`);
  }
}

function formatSize(bytes) {
  if (!bytes || bytes <= 0) return "0 B";
  const mb = bytes / (1024 * 1024);
  if (mb >= 1024) return `${(mb / 1024).toFixed(2)} GB`;
  return `${mb.toFixed(0)} MB`;
}
</script>
