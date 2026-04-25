<template>
  <div class="space-y-4">
    <div class="flex items-start justify-between gap-4">
      <div>``
        <p class="text-sm text-gray-500 mt-1">输入文案 + 上传A/B/C角色素材，自动拆句、分配角色并生成混剪预览与MP4。</p>
      </div>
      <div class="flex items-center gap-2">
        <el-button :loading="loading.oneClick" :disabled="!roughCutEnabled" type="primary" @click="oneClickRoughCut">一键混剪</el-button>
        <el-button :loading="loading.regenerate" @click="regenerateAll">重新生成</el-button>
        <el-button :disabled="!project" @click="project && openCompareDialog(project.id)">匹配对比</el-button>
        <el-button :loading="loading.exportFinal" :disabled="!project" @click="exportFinal">导出 MP4</el-button>
      </div>
    </div>
    <div v-if="!roughCutEnabled && roughCutEnabledReason" class="text-xs text-amber-600">
      {{ roughCutEnabledReason }}
    </div>

    <div class="grid grid-cols-12 gap-4">
      <section class="col-span-12 xl:col-span-3 space-y-4">
        <div class="rounded-xl border border-gray-200 bg-white p-4 shadow-card space-y-3">
          <div class="flex items-center justify-between gap-2">
            <div class="text-sm font-semibold">项目与文案</div>
            <el-button size="small" @click="createProjectWithDraft">新建项目</el-button>
          </div>
          <el-select
            v-model="currentProjectId"
            class="w-full"
            placeholder="选择混剪项目"
            filterable
            @change="onProjectChange"
          >
            <el-option
              v-for="item in projects"
              :key="item.id"
              :label="`${item.title} (#${item.id})`"
              :value="item.id"
            />
          </el-select>
          <el-input v-model="newProjectTitle" placeholder="项目标题（可选）" />
          <el-input
            v-model="scriptDraft"
            type="textarea"
            :rows="8"
            placeholder="请粘贴口播文案，支持换行与标点自动拆句"
          />
          <div class="flex items-center gap-2">
            <el-button :loading="loading.splitScript" @click="splitScript">自动拆句</el-button>
            <el-button :loading="loading.buildTimeline" @click="buildTimelineOnly">生成时间线</el-button>
          </div>
        </div>
      </section>

      <section class="col-span-12 xl:col-span-6 space-y-4">
        <div class="rounded-xl border border-gray-200 bg-white p-4 shadow-card">
          <div class="flex items-center justify-between mb-2">
            <div class="text-sm font-semibold">预览播放器</div>
            <el-tag size="small" :type="statusTagType">{{ statusText }}</el-tag>
          </div>
          <div class="mb-3">
            <div class="flex items-center justify-between text-xs text-gray-600 mb-1">
              <span>任务进度</span>
              <span>{{ pipelineProgress }}%</span>
            </div>
            <el-progress
              :percentage="pipelineProgress"
              :stroke-width="14"
              :class="project?.status === 'processing' || hasAsrRunning ? 'progress-breathing' : ''"
            />
            <div v-if="asrProgressSummary.length" class="mt-2 grid grid-cols-3 gap-2 text-[11px] text-gray-600">
              <div v-for="item in asrProgressSummary" :key="item.roleId" class="rounded border border-gray-200 px-2 py-1">
                {{ item.roleId }}: {{ item.progress }}% / 匹配 {{ item.matchPercent }}%
              </div>
            </div>
          </div>
          <div class="rounded-lg border border-gray-200 bg-black overflow-hidden">
            <div class="relative w-3/4 mx-auto">
            <video
              v-if="currentMediaUrl"
              :key="currentMediaUrl"
              ref="videoRef"
              class="w-full max-h-[420px]"
              :src="currentMediaUrl"
              controls
              preload="metadata"
              @timeupdate="onVideoTimeUpdate"
              @loadedmetadata="onVideoLoadedMetadata"
            />
            <div v-else class="w-full min-h-[420px] bg-black" />
            <div
              v-if="previewBusy"
              class="absolute inset-0 flex flex-col items-center justify-center bg-black/60 text-white backdrop-blur-sm"
            >
              <div class="loading-dots">
                <span />
                <span />
                <span />
              </div>
              <div class="mt-4 text-sm">正在生成最新预览视频</div>
            </div>
            </div>
          </div>
          <div class="mt-3 grid grid-cols-1 md:grid-cols-2 gap-2 text-xs text-gray-600">
            <div>当前句子：{{ activeSentenceText || "未选择" }}</div>
            <div>当前素材：{{ activeSentenceAsset || "-" }}</div>
            <div>时间段：{{ activeSentenceRange || "-" }}</div>
            <div>输出：{{ project?.outputUrl ? "可下载MP4" : "未导出" }}</div>
          </div>
        </div>

        <div class="rounded-xl border border-gray-200 bg-white p-4 shadow-card">
          <div class="flex items-center justify-between mb-3">
            <div class="text-sm font-semibold">时间线</div>
            <div class="text-xs text-gray-500">点击片段可定位对应句子</div>
          </div>
          <div v-if="timeline.length === 0" class="text-sm text-gray-500">尚未生成时间线。</div>
          <div v-else class="space-y-2">
            <div class="flex h-6 rounded-lg overflow-hidden border border-gray-200">
              <div
                v-for="clip in timeline"
                :key="clip.id"
                class="h-full cursor-pointer transition hover:brightness-110"
                :style="timelineClipStyle(clip)"
                :title="timelineTitle(clip)"
                @click="selectSentenceFromTimeline(clip)"
              />
            </div>
            <el-slider
              v-model="timelineSliderTime"
              :min="0"
              :max="Math.max(0.1, totalTimelineSeconds)"
              :step="0.01"
              :show-tooltip="false"
              @input="onTimelineSliderInput"
              @change="onTimelineSliderChange"
            />
            <div class="text-xs text-gray-500">
              总时长：{{ formatSeconds(totalTimelineSeconds) }} ｜ 当前：{{ formatSeconds(timelineSliderTime) }}
            </div>
          </div>
        </div>

        <div class="rounded-xl border border-gray-200 bg-white p-4 shadow-card">
          <div class="flex items-center justify-between mb-3">
            <div class="text-sm font-semibold">句子列表</div>
            <div class="text-xs text-gray-500">{{ sentences.length }} 句</div>
          </div>
          <div v-if="sentences.length === 0" class="text-sm text-gray-500">请先输入文案并点击“自动拆句”。</div>
          <div v-else class="space-y-2 max-h-[36vh] overflow-auto pr-1">
            <div
              v-for="sentence in sentences"
              :key="sentence.id"
              class="rounded-lg border p-3 transition"
              :class="selectedSentenceId === sentence.id ? 'border-black bg-gray-50' : 'border-gray-200 bg-white'"
            >
              <div class="flex items-start justify-between gap-2">
                <div class="text-xs text-gray-500">#{{ sentence.index }}</div>
                <el-tag size="small" :style="{ backgroundColor: roleColor(sentence.roleId), color: '#fff', border: 'none' }">
                  {{ sentence.roleId || "未分配" }}
                </el-tag>
              </div>
              <div class="text-sm mt-1 whitespace-pre-wrap break-words">{{ sentence.text }}</div>

              <div class="mt-2 grid grid-cols-2 gap-2">
                <el-select v-model="sentence.roleId" size="small">
                  <el-option v-for="role in roles" :key="role.id" :label="role.id" :value="role.id" />
                </el-select>
                <el-input-number
                  v-model="sentence.estimatedDuration"
                  size="small"
                  :min="0.8"
                  :max="8"
                  :step="0.1"
                  :precision="1"
                  controls-position="right"
                />
              </div>

              <div class="mt-2 flex items-center justify-between gap-2">
                <el-switch v-model="sentence.locked" size="small" active-text="锁定" inactive-text="未锁定" />
                <div class="flex items-center gap-1">
                  <el-button
                    size="small"
                    text
                    :loading="sentenceLoading[sentence.id] === 'save'"
                    @click="saveSentence(sentence)"
                  >
                    保存
                  </el-button>
                  <el-button size="small" text @click="previewSentence(sentence)">预览本句</el-button>
                  <el-button
                    size="small"
                    text
                    :loading="sentenceLoading[sentence.id] === 'regen'"
                    @click="regenerateSentence(sentence)"
                  >
                    重生本句
                  </el-button>
                </div>
              </div>

              <div class="text-xs text-gray-500 mt-1">
                {{ sentenceClipText(sentence.id) }}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section class="col-span-12 xl:col-span-3 space-y-4">
        <div class="rounded-xl border border-gray-200 bg-white p-4 shadow-card">
          <el-collapse v-model="activePanels">
            <el-collapse-item title="角色规则" name="roles">
              <div class="space-y-3">
                <el-select v-model="roleForm.strategy" class="w-full">
                  <el-option label="自动轮播" value="auto" />
                  <el-option label="主角色优先" value="primary-first" />
                  <el-option label="指定序列" value="manual-sequence" />
                </el-select>
                <el-select v-model="roleForm.primaryRoleId" class="w-full" placeholder="主角色">
                  <el-option v-for="role in roles" :key="role.id" :label="role.id" :value="role.id" />
                </el-select>
                <el-input
                  v-if="roleForm.strategy === 'manual-sequence'"
                  v-model="roleForm.manualSequence"
                  placeholder="A+B+A+C+A"
                />
                <el-button class="w-full" :loading="loading.assignRoles" @click="assignRoles">应用角色分配</el-button>
              </div>
            </el-collapse-item>

            <el-collapse-item title="生成参数" name="settings">
              <div class="space-y-2">
                <el-select v-model="renderForm.aspectRatio" class="w-full">
                  <el-option label="9:16" value="9:16" />
                  <el-option label="16:9" value="16:9" />
                  <el-option label="1:1" value="1:1" />
                </el-select>
                <el-select v-model="renderForm.resolution" class="w-full">
                  <el-option label="720p" value="720p" />
                  <el-option label="1080p" value="1080p" />
                </el-select>
                <el-select v-model="renderForm.fps" class="w-full">
                  <el-option label="25" :value="25" />
                  <el-option label="30" :value="30" />
                </el-select>
                <el-select v-model="renderForm.audioMode" class="w-full">
                  <el-option label="保留原音" value="keep" />
                  <el-option label="静音" value="mute" />
                  <el-option label="TTS占位" value="tts" />
                </el-select>
                <el-select v-model="renderForm.subtitleMode" class="w-full">
                  <el-option label="关闭" value="off" />
                  <el-option label="SRT" value="srt" />
                  <el-option label="烧录" value="burn" />
                </el-select>
                <el-select v-model="renderForm.transitionMode" class="w-full">
                  <el-option label="无" value="none" />
                  <el-option label="淡入淡出" value="fade" />
                </el-select>
                <el-button class="w-full" :loading="loading.updateSettings" @click="applySettings">保存生成参数</el-button>
              </div>
            </el-collapse-item>

            <el-collapse-item title="角色素材库" name="assets">
              <div class="space-y-4">
                <div v-for="role in roles" :key="role.id" class="border border-gray-200 rounded-lg p-2">
                  <div class="flex items-center justify-between mb-2">
                    <div class="text-sm font-medium" :style="{ color: role.color || '#333' }">角色 {{ role.id }}</div>
                    <div class="text-xs text-gray-500">{{ roleAsset(role.id) ? "已上传 1 个" : "未上传" }}</div>
                  </div>
                  <FileUpload
                    :title="`上传 ${role.id} 素材`"
                    hint="单角色仅保留1个视频，上传新视频会自动替换旧视频"
                    accept="video/*"
                    :multiple="false"
                    :limit="1"
                    @update:files="(files) => updateRoleUpload(role.id, files)"
                  />
                  <div class="mt-2 flex items-center justify-end">
                    <el-button
                      size="small"
                      :loading="uploadLoading[role.id]"
                      @click="uploadRoleAssets(role.id)"
                    >
                      上传到角色{{ role.id }}
                    </el-button>
                  </div>
                  <div class="mt-2">
                    <div
                      v-if="roleAsset(role.id)"
                      class="text-xs text-gray-600 bg-gray-50 rounded px-2 py-2 border border-gray-200"
                    >
                      <div class="font-medium truncate" :title="roleAsset(role.id).fileName">{{ roleAsset(role.id).fileName }}</div>
                      <div class="text-gray-500 mt-1">
                        {{ formatSeconds(roleAsset(role.id).duration) }} · {{ roleAsset(role.id).width }}x{{ roleAsset(role.id).height }}
                      </div>
                      <div class="mt-1 text-gray-500">
                        ASR: {{ roleAsset(role.id).asrStatus || "pending" }} · {{ roleAsset(role.id).asrProgress || 0 }}%
                      </div>
                      <div class="mt-1 text-gray-500">
                        匹配率: {{ Number(roleAsset(role.id).matchPercent || 0).toFixed(1) }}%
                      </div>
                      <el-progress
                        class="mt-2"
                        :percentage="Math.max(0, Math.min(100, Number(roleAsset(role.id).asrProgress || 0)))"
                        :stroke-width="8"
                        :class="['pending', 'running'].includes(String(roleAsset(role.id).asrStatus || '').toLowerCase()) ? 'progress-breathing' : ''"
                      />
                      <div class="mt-2 flex items-center gap-2">
                        <el-button size="small" text @click="previewAsset(roleAsset(role.id))">预览</el-button>
                        <el-button
                          size="small"
                          text
                          type="danger"
                          :loading="assetActionLoading[roleAsset(role.id).id] === 'remove'"
                          @click="removeAsset(roleAsset(role.id))"
                        >
                          删除素材
                        </el-button>
                      </div>
                    </div>
                    <div v-else class="text-xs text-gray-500 bg-gray-50 rounded px-2 py-2 border border-dashed border-gray-200">
                      当前角色暂无素材
                    </div>
                  </div>
                </div>
              </div>
            </el-collapse-item>

            <el-collapse-item title="导出与日志" name="progress">
              <div class="space-y-3">
                <el-progress
                  :percentage="project?.progress || 0"
                  :status="project?.status === 'error' ? 'exception' : project?.status === 'ready' ? 'success' : ''"
                  :stroke-width="16"
                  :class="project?.status === 'processing' ? 'progress-breathing' : ''"
                />
                <div class="text-xs text-gray-600">阶段：{{ project?.phase || "-" }}</div>
                <el-input
                  type="textarea"
                  :rows="8"
                  readonly
                  :model-value="project?.log || '暂无日志'"
                />
                <div class="flex items-center gap-2">
                  <el-button size="small" :disabled="!project?.previewUrl" @click="refreshPreview">刷新预览</el-button>
                  <el-button size="small" :disabled="!project?.outputUrl" @click="downloadOutput">下载MP4</el-button>
                </div>
              </div>
            </el-collapse-item>
          </el-collapse>
        </div>
      </section>
    </div>

    <el-dialog
      v-model="assetPreview.visible"
      :title="assetPreview.title || '素材预览'"
      width="760px"
      destroy-on-close
      align-center
    >
      <video
        v-if="assetPreview.visible && assetPreview.url"
        :src="assetPreview.url"
        controls
        preload="metadata"
        class="w-full max-h-[60vh] rounded"
      />
    </el-dialog>

    <el-dialog
      v-model="compareDialog.visible"
      title="ASR匹配对比中心"
      width="90vw"
      destroy-on-close
      align-center
      top="4vh"
    >
      <div class="mb-2 flex items-center justify-between text-xs text-gray-600">
        <span>角色ASR完成后自动弹出；匹配率需达到95%才能执行一键混剪。</span>
        <span v-if="currentCompareRole">
          匹配率 {{ Number(currentCompareRole.matchPercent || 0).toFixed(1) }}% ·
          <span :class="currentCompareRole.gatePassed ? 'text-emerald-600' : 'text-rose-600'">
            {{ currentCompareRole.gatePassed ? "通过" : "未通过" }}
          </span>
        </span>
      </div>
      <el-tabs v-model="compareDialog.activeProjectId" @tab-change="onCompareProjectTabChange">
        <el-tab-pane
          v-for="pane in compareDialog.projectTabs"
          :key="pane.projectId"
          :label="pane.projectTitle"
          :name="String(pane.projectId)"
        >
          <el-tabs v-model="compareDialog.activeRoleId">
            <el-tab-pane
              v-for="role in pane.roles"
              :key="role.roleId"
              :label="`${role.roleId} (${Number(role.matchPercent || 0).toFixed(1)}%)`"
              :name="role.roleId"
            >
              <div class="grid grid-cols-1 lg:grid-cols-2 gap-3">
                <div class="rounded border border-gray-200 bg-gray-50 p-3">
                  <div class="mb-2 text-xs font-medium text-gray-700">主文本（角色句子）</div>
                  <div class="h-[42vh] overflow-auto text-sm leading-6 whitespace-pre-wrap break-words" v-html="currentCompareMainHtml" />
                </div>
                <div class="rounded border border-gray-200 bg-gray-50 p-3">
                  <div class="mb-2 text-xs font-medium text-gray-700">ASR文本（识别结果）</div>
                  <div class="h-[42vh] overflow-auto text-sm leading-6 whitespace-pre-wrap break-words" v-html="currentCompareAsrHtml" />
                </div>
              </div>
              <div class="mt-3 grid grid-cols-2 md:grid-cols-5 gap-2 text-xs">
                <div class="rounded border border-gray-200 px-2 py-1">匹配字数: {{ Number(role.matchedChars || 0) }}</div>
                <div class="rounded border border-gray-200 px-2 py-1">SRT总字数: {{ Number(role.srtTotalChars || 0) }}</div>
                <div class="rounded border border-gray-200 px-2 py-1">匹配率: {{ Number(role.matchPercent || 0).toFixed(1) }}%</div>
                <div class="rounded border border-gray-200 px-2 py-1">ASR状态: {{ role.asrStatus || "-" }}</div>
                <div class="rounded border border-gray-200 px-2 py-1">ASR进度: {{ Number(role.asrProgress || 0) }}%</div>
              </div>
              <div v-if="role.asrError" class="mt-2 text-xs text-rose-600">错误: {{ role.asrError }}</div>
            </el-tab-pane>
          </el-tabs>
        </el-tab-pane>
      </el-tabs>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import FileUpload from "../components/common/FileUpload.vue";
import {
  assignRoughCutRoles,
  buildRoughCutTimeline,
  createRoughCutProject,
  deleteRoughCutAsset,
  exportRoughCutProject,
  getRoughCutAssetMediaUrl,
  getRoughCutProjectCompare,
  getRoughCutProject,
  listRoughCutProjects,
  splitRoughCutScript,
  updateRoughCutSentence,
  updateRoughCutSettings,
  uploadRoughCutAssets,
  regenerateRoughCutSentence,
} from "../api/roughCut";

const loading = reactive({
  oneClick: false,
  regenerate: false,
  splitScript: false,
  assignRoles: false,
  buildTimeline: false,
  updateSettings: false,
  exportFinal: false,
});

const projects = ref([]);
const currentProjectId = ref(null);
const project = ref(null);
const newProjectTitle = ref("");
const scriptDraft = ref("");
const activePanels = ref(["roles", "settings", "assets", "progress"]);
const selectedSentenceId = ref("");
const videoRef = ref(null);
const statusPollTimer = ref(null);
const timelineSliderTime = ref(0);
const isDraggingTimelineSlider = ref(false);
const lastMatchWarningKey = ref("");
const sentenceLoading = reactive({});
const uploadLoading = reactive({});
const roleUploadFiles = reactive({});
const assetActionLoading = reactive({});
const assetPreview = reactive({
  visible: false,
  title: "",
  url: "",
});
const compareDialog = reactive({
  visible: false,
  activeProjectId: "",
  activeRoleId: "",
  projectTabs: [],
});
const compareCache = reactive({});
const roleAsrStatusMemory = reactive({});
const seenComparePopupKeys = reactive({});

const roleForm = reactive({
  strategy: "primary-first",
  manualSequence: "",
  primaryRoleId: "A",
});

const renderForm = reactive({
  aspectRatio: "9:16",
  resolution: "1080p",
  fps: 30,
  audioMode: "keep",
  subtitleMode: "off",
  transitionMode: "none",
});

const roles = computed(() => project.value?.roles || []);
const sentences = computed(() => project.value?.sentences || []);
const timeline = computed(() => project.value?.timeline || []);
const totalTimelineSeconds = computed(() =>
  timeline.value.reduce((acc, item) => Math.max(acc, Number(item.timelineEnd || 0)), 0)
);
const previewBusy = computed(() =>
  !!(
    loading.oneClick ||
    loading.regenerate ||
    loading.buildTimeline ||
    project.value?.status === "processing"
  )
);
const currentMediaUrl = computed(() => {
  const base = project.value?.outputUrl || project.value?.previewUrl || "";
  if (!base || previewBusy.value) return "";
  const stamp = encodeURIComponent(
    `${project.value?.updatedAt || ""}_${project.value?.status || ""}_${project.value?.progress || 0}`
  );
  return `${base}${base.includes("?") ? "&" : "?"}v=${stamp}`;
});
const pipelineProgress = computed(() => {
  const raw = Number(project.value?.pipelineProgress ?? project.value?.progress ?? 0);
  if (!Number.isFinite(raw)) return 0;
  return Math.max(0, Math.min(100, Math.round(raw)));
});
const asrProgressSummary = computed(() => {
  const rows = Array.isArray(project.value?.rolesAsrProgress) ? project.value.rolesAsrProgress : [];
  return rows.map((item) => ({
    roleId: item.roleId || "-",
    progress: Math.max(0, Math.min(100, Number(item.progress || 0))),
    matchPercent: Number(item.matchPercent || 0).toFixed(1),
    status: item.status || "pending",
  }));
});
const hasAsrRunning = computed(() => asrProgressSummary.value.some((item) => ["pending", "running"].includes(String(item.status))));
const roughCutEnabled = computed(() => !!project.value?.roughCutEnabled);
const roughCutEnabledReason = computed(() => String(project.value?.roughCutEnabledReason || "").trim());
const currentCompareProject = computed(() =>
  compareDialog.projectTabs.find((item) => String(item.projectId) === String(compareDialog.activeProjectId)) || null
);
const currentCompareRole = computed(() =>
  currentCompareProject.value?.roles?.find((item) => item.roleId === compareDialog.activeRoleId) || null
);
const currentCompareMainHtml = computed(() =>
  buildLcsHighlightedHtml(
    String(currentCompareRole.value?.mainText || ""),
    String(currentCompareRole.value?.asrText || ""),
    "main"
  )
);
const currentCompareAsrHtml = computed(() =>
  buildLcsHighlightedHtml(
    String(currentCompareRole.value?.mainText || ""),
    String(currentCompareRole.value?.asrText || ""),
    "asr"
  )
);

const statusTagType = computed(() => {
  const status = project.value?.status;
  if (status === "ready") return "success";
  if (status === "processing") return "warning";
  if (status === "error") return "danger";
  return "info";
});

const statusText = computed(() => {
  const status = project.value?.status;
  if (status === "ready") return "已就绪";
  if (status === "processing") return "处理中";
  if (status === "error") return "失败";
  return "未开始";
});

const activeSentence = computed(() => {
  if (!selectedSentenceId.value) return null;
  return sentences.value.find((item) => item.id === selectedSentenceId.value) || null;
});

const activeSentenceText = computed(() => activeSentence.value?.text || "");
const activeSentenceRange = computed(() => {
  if (!activeSentence.value) return "";
  const range = sentenceRange(activeSentence.value.id);
  if (!range) return "";
  return `${formatSeconds(range.start)} - ${formatSeconds(range.end)}`;
});
const activeSentenceAsset = computed(() => {
  if (!activeSentence.value) return "";
  const clips = sentenceClips(activeSentence.value.id);
  if (clips.length === 0) return "";
  const clip = clips[0];
  const path = String(clip.filePath || "");
  return path ? path.split("/").pop() : "";
});

onMounted(async () => {
  await refreshProjectList();
});

onBeforeUnmount(() => {
  stopStatusPolling();
});

watch(currentProjectId, async (id) => {
  if (!id) return;
  await loadProject(id);
});

watch(
  () => [project.value?.status, hasAsrRunning.value],
  ([status, asrRunning]) => {
    if (status === "processing" || asrRunning) {
      startStatusPolling();
      return;
    }
    if (status === "ready" || status === "error" || status === "idle") {
      stopStatusPolling();
    }
  }
);

watch(
  () => totalTimelineSeconds.value,
  (seconds) => {
    if (!Number.isFinite(seconds) || seconds <= 0) {
      timelineSliderTime.value = 0;
      return;
    }
    if (timelineSliderTime.value > seconds) {
      timelineSliderTime.value = seconds;
    }
  }
);

watch(
  () => project.value?.assets,
  (assets) => {
    const list = Array.isArray(assets) ? assets : [];
    const warningTargets = list
      .filter(
        (item) =>
          String(item?.asrStatus || "").toLowerCase() === "completed" &&
          Number(item?.matchPercent || 0) < 80
      )
      .map((item) => `${item.roleId}:${item.matchPercent}`);
    const warningKey = warningTargets.join("|");
    if (!warningKey || warningKey === lastMatchWarningKey.value) return;
    lastMatchWarningKey.value = warningKey;
    ElMessageBox.alert(
      "上传视频与文案匹配度必须超过95%才能进行混剪。",
      "匹配度不足",
      { type: "warning" }
    ).catch(() => {});
  },
  { deep: true }
);

function escapeHtml(raw) {
  return String(raw || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function buildLcsMasks(textA, textB) {
  const a = Array.from(String(textA || ""));
  const b = Array.from(String(textB || ""));
  const rows = a.length + 1;
  const cols = b.length + 1;
  const dp = Array.from({ length: rows }, () => Array(cols).fill(0));

  for (let i = 1; i < rows; i += 1) {
    for (let j = 1; j < cols; j += 1) {
      if (a[i - 1] === b[j - 1]) dp[i][j] = dp[i - 1][j - 1] + 1;
      else dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
    }
  }

  const maskA = Array(a.length).fill(false);
  const maskB = Array(b.length).fill(false);
  let i = a.length;
  let j = b.length;
  while (i > 0 && j > 0) {
    if (a[i - 1] === b[j - 1]) {
      maskA[i - 1] = true;
      maskB[j - 1] = true;
      i -= 1;
      j -= 1;
    } else if (dp[i - 1][j] >= dp[i][j - 1]) i -= 1;
    else j -= 1;
  }
  return { charsA: a, charsB: b, maskA, maskB };
}

function maskCharsToHtml(chars, mask) {
  const htmlParts = [];
  for (let idx = 0; idx < chars.length; idx += 1) {
    const escaped = escapeHtml(chars[idx]);
    if (mask[idx]) htmlParts.push(`<span class="bg-amber-200 text-amber-900 rounded-sm">${escaped}</span>`);
    else htmlParts.push(escaped);
  }
  return htmlParts.join("");
}

function buildLcsHighlightedHtml(mainText, asrText, target) {
  const { charsA, charsB, maskA, maskB } = buildLcsMasks(mainText, asrText);
  if (target === "main") return maskCharsToHtml(charsA, maskA);
  return maskCharsToHtml(charsB, maskB);
}

function setActiveRoleForProject(projectId, roleId = "") {
  const pane = compareDialog.projectTabs.find((item) => String(item.projectId) === String(projectId));
  if (!pane || !Array.isArray(pane.roles) || !pane.roles.length) {
    compareDialog.activeRoleId = "";
    return;
  }
  const exists = pane.roles.some((item) => item.roleId === roleId);
  compareDialog.activeRoleId = exists ? roleId : pane.roles[0].roleId;
}

function upsertCompareProject(comparePayload, loaded = false) {
  if (!comparePayload || !comparePayload.projectId) return;
  const payload = { ...comparePayload, _loaded: loaded || !!comparePayload._loaded };
  compareCache[payload.projectId] = payload;
  const existingIndex = compareDialog.projectTabs.findIndex(
    (item) => String(item.projectId) === String(payload.projectId)
  );
  if (existingIndex >= 0) compareDialog.projectTabs[existingIndex] = payload;
  else compareDialog.projectTabs.push(payload);
}

async function ensureCompareProjectLoaded(projectId) {
  if (!projectId) return null;
  const cached = compareCache[projectId];
  if (cached && cached._loaded) return cached;
  const data = await getRoughCutProjectCompare(projectId);
  upsertCompareProject(data, true);
  return data;
}

function refreshCompareProjectTabsFromList() {
  const fromList = Array.isArray(projects.value) ? projects.value : [];
  const nextTabs = fromList.map((item) => {
    const cached = compareCache[item.id];
    return {
      projectId: item.id,
      projectTitle: item.title || `项目#${item.id}`,
      roles: cached?.roles || [],
      _loaded: !!cached?._loaded,
    };
  });
  compareDialog.projectTabs = nextTabs;
}

async function openCompareDialog(projectId, roleId = "") {
  refreshCompareProjectTabsFromList();
  const comparePayload = await ensureCompareProjectLoaded(projectId);
  if (!comparePayload) return;
  compareDialog.activeProjectId = String(projectId);
  setActiveRoleForProject(projectId, roleId);
  compareDialog.visible = true;
}

function rememberRoleAsrStatus(projectPayload) {
  if (!projectPayload?.id) return;
  const projectId = String(projectPayload.id);
  if (!roleAsrStatusMemory[projectId]) roleAsrStatusMemory[projectId] = {};
  const statusMap = roleAsrStatusMemory[projectId];
  const assets = Array.isArray(projectPayload.assets) ? projectPayload.assets : [];
  assets.forEach((asset) => {
    const roleId = String(asset?.roleId || "").trim();
    if (!roleId) return;
    statusMap[roleId] = String(asset?.asrStatus || "").toLowerCase();
  });
}

async function handleAsrCompletionAutoPopup(projectPayload) {
  if (!projectPayload?.id) return;
  const projectId = String(projectPayload.id);
  if (!roleAsrStatusMemory[projectId]) roleAsrStatusMemory[projectId] = {};
  const statusMap = roleAsrStatusMemory[projectId];
  const assets = Array.isArray(projectPayload.assets) ? projectPayload.assets : [];

  for (const asset of assets) {
    const roleId = String(asset?.roleId || "").trim();
    if (!roleId) continue;
    const currentStatus = String(asset?.asrStatus || "").toLowerCase();
    const previousStatus = String(statusMap[roleId] || "");
    const asrVersionKey = String(asset?.asrSrtPath || `${asset?.asrProgress || 0}_${asset?.matchedChars || 0}`);
    const popupKey = `${projectId}_${roleId}_${asrVersionKey}`;
    statusMap[roleId] = currentStatus;

    const transitionedToCompleted =
      currentStatus === "completed" &&
      previousStatus &&
      previousStatus !== "completed";
    if (!transitionedToCompleted) continue;
    if (seenComparePopupKeys[popupKey]) continue;
    seenComparePopupKeys[popupKey] = true;

    try {
      await openCompareDialog(projectPayload.id, roleId);
    } catch (_error) {
      // ignore popup load error
    }
    break;
  }
}

function nowProjectTitle() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `口播混剪_${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
}

function roleColor(roleId) {
  const role = roles.value.find((item) => item.id === roleId);
  return role?.color || "#111827";
}

function formatSeconds(value) {
  const sec = Number(value);
  if (!Number.isFinite(sec)) return "00:00";
  const min = Math.floor(sec / 60);
  const remain = Math.floor(sec % 60);
  return `${String(min).padStart(2, "0")}:${String(remain).padStart(2, "0")}`;
}

function sentenceClips(sentenceId) {
  return timeline.value.filter((item) => item.sentenceId === sentenceId);
}

function sentenceRange(sentenceId) {
  const clips = sentenceClips(sentenceId);
  if (clips.length === 0) return null;
  return {
    start: Math.min(...clips.map((item) => Number(item.timelineStart || 0))),
    end: Math.max(...clips.map((item) => Number(item.timelineEnd || 0))),
  };
}

function sentenceClipText(sentenceId) {
  const clips = sentenceClips(sentenceId);
  if (clips.length === 0) return "素材：未生成";
  const clip = clips[0];
  const range = sentenceRange(sentenceId);
  const fileName = String(clip.filePath || "").split("/").pop();
  return `素材：${fileName} ${formatSeconds(clip.sourceStart)}-${formatSeconds(clip.sourceEnd)} ｜ 时间线 ${formatSeconds(range.start)}-${formatSeconds(range.end)}`;
}

function roleAssets(roleId) {
  const assets = project.value?.assets || [];
  return assets.filter((item) => item.roleId === roleId);
}

function roleAsset(roleId) {
  const assets = roleAssets(roleId);
  if (!assets.length) return null;
  return assets[assets.length - 1];
}

function timelineTitle(clip) {
  const sentence = sentences.value.find((item) => item.id === clip.sentenceId);
  const role = clip.roleId || "-";
  return `句子#${sentence?.index || "-"} ${role} ${formatSeconds(clip.duration)} ${sentence?.text || ""}`;
}

function timelineClipStyle(clip) {
  const total = Math.max(0.1, totalTimelineSeconds.value);
  const width = Math.max(3, (Number(clip.duration || 0) / total) * 100);
  return {
    width: `${width}%`,
    backgroundColor: roleColor(clip.roleId),
    borderRight: "1px solid rgba(255,255,255,0.35)",
  };
}

function selectSentenceFromTimeline(clip) {
  selectedSentenceId.value = clip.sentenceId;
  previewSentenceById(clip.sentenceId);
}

function previewSentence(sentence) {
  selectedSentenceId.value = sentence.id;
  previewSentenceById(sentence.id);
}

function previewSentenceById(sentenceId) {
  const range = sentenceRange(sentenceId);
  if (!range || !videoRef.value) return;
  try {
    videoRef.value.currentTime = Math.max(0, range.start);
    timelineSliderTime.value = Math.max(0, range.start);
    videoRef.value.play();
  } catch (_error) {
    // Ignore autoplay errors.
  }
}

function onVideoLoadedMetadata() {
  if (!videoRef.value) return;
  timelineSliderTime.value = Math.max(0, Number(videoRef.value.currentTime || 0));
}

function onVideoTimeUpdate() {
  if (!videoRef.value || isDraggingTimelineSlider.value) return;
  timelineSliderTime.value = Math.max(0, Number(videoRef.value.currentTime || 0));
}

function onTimelineSliderInput(value) {
  isDraggingTimelineSlider.value = true;
  timelineSliderTime.value = Number(value || 0);
}

function onTimelineSliderChange(value) {
  timelineSliderTime.value = Number(value || 0);
  if (videoRef.value) {
    videoRef.value.currentTime = timelineSliderTime.value;
  }
  isDraggingTimelineSlider.value = false;
}

async function refreshProjectList(selectId = null) {
  const items = await listRoughCutProjects();
  projects.value = items;
  if (items.length === 0) {
    currentProjectId.value = null;
    project.value = null;
    scriptDraft.value = "";
    return;
  }

  const targetId = selectId || currentProjectId.value || items[0].id;
  currentProjectId.value = items.some((item) => item.id === targetId) ? targetId : items[0].id;
}

async function loadProject(projectId) {
  project.value = await getRoughCutProject(projectId);
  scriptDraft.value = project.value.script || "";
  syncFormsFromProject();
  rememberRoleAsrStatus(project.value);
  await handleAsrCompletionAutoPopup(project.value);
  if (!isDraggingTimelineSlider.value && videoRef.value) {
    timelineSliderTime.value = Math.max(0, Number(videoRef.value.currentTime || 0));
  }
}

async function onCompareProjectTabChange(projectId) {
  const id = String(projectId || "").trim();
  if (!id) return;
  const loaded = await ensureCompareProjectLoaded(Number(id));
  if (!loaded) return;
  setActiveRoleForProject(Number(id));
}

function syncFormsFromProject() {
  if (!project.value) return;
  const settings = project.value.settings || {};
  renderForm.aspectRatio = settings.aspectRatio || "9:16";
  renderForm.resolution = settings.resolution || "1080p";
  renderForm.fps = settings.fps || 30;
  renderForm.audioMode = settings.audioMode || "keep";
  renderForm.subtitleMode = settings.subtitleMode || "off";
  renderForm.transitionMode = settings.transitionMode || "none";

  roleForm.strategy = settings.roleStrategy || "primary-first";
  roleForm.manualSequence = settings.manualSequence || "";
  roleForm.primaryRoleId = settings.primaryRoleId || roles.value[0]?.id || "A";
}

async function createProjectWithDraft() {
  const payload = {
    title: (newProjectTitle.value || "").trim() || nowProjectTitle(),
    script: scriptDraft.value || "",
  };
  const created = await createRoughCutProject(payload);
  await refreshProjectList(created.id);
  await loadProject(created.id);
  ElMessage.success("已创建混剪项目");
}

async function ensureProject() {
  if (project.value?.id) return project.value;
  await createProjectWithDraft();
  return project.value;
}

function normalizedSettingsPayload() {
  return {
    aspectRatio: renderForm.aspectRatio,
    resolution: renderForm.resolution,
    fps: Number(renderForm.fps),
    audioMode: renderForm.audioMode,
    subtitleMode: renderForm.subtitleMode,
    transitionMode: renderForm.transitionMode,
    roleStrategy: roleForm.strategy,
    manualSequence: roleForm.manualSequence || null,
    primaryRoleId: roleForm.primaryRoleId || roles.value[0]?.id || "A",
  };
}

async function applySettings(silent = false) {
  loading.updateSettings = true;
  try {
    const current = await ensureProject();
    project.value = await updateRoughCutSettings(current.id, normalizedSettingsPayload());
    if (!silent) ElMessage.success("生成参数已保存");
  } finally {
    loading.updateSettings = false;
  }
}

async function splitScript(silent = false) {
  loading.splitScript = true;
  try {
    const current = await ensureProject();
    project.value = await splitRoughCutScript(current.id, scriptDraft.value || "");
    if (!silent) ElMessage.success("脚本拆句完成");
  } finally {
    loading.splitScript = false;
  }
}

async function assignRoles(silent = false) {
  loading.assignRoles = true;
  try {
    const current = await ensureProject();
    project.value = await assignRoughCutRoles(current.id, {
      strategy: roleForm.strategy,
      manualSequence: roleForm.strategy === "manual-sequence" ? roleForm.manualSequence : null,
      primaryRoleId: roleForm.primaryRoleId || roles.value[0]?.id || "A",
    });
    if (!silent) ElMessage.success("角色分配完成");
  } finally {
    loading.assignRoles = false;
  }
}

async function syncAllSentencesBeforeRender() {
  const current = await ensureProject();
  const draftSentences = sentences.value.map((sentence) => ({
    id: sentence.id,
    roleId: sentence.roleId || null,
    estimatedDuration: Number(sentence.estimatedDuration || 0),
    locked: !!sentence.locked,
  }));

  let latest = null;
  for (const draft of draftSentences) {
    latest = await updateRoughCutSentence(current.id, draft.id, {
      roleId: draft.roleId,
      estimatedDuration: draft.estimatedDuration,
      locked: draft.locked,
    });
  }
  if (latest) {
    project.value = latest;
  }
}

async function buildTimelineOnly(silent = false) {
  loading.buildTimeline = true;
  try {
    await syncAllSentencesBeforeRender();
    const current = await ensureProject();
    project.value = await buildRoughCutTimeline(current.id, true);
    if (!silent) ElMessage.success("时间线已生成");
  } finally {
    loading.buildTimeline = false;
  }
}

async function startExport(mode, silent = false) {
  const current = await ensureProject();
  await exportRoughCutProject(current.id, mode);
  project.value = {
    ...project.value,
    status: "processing",
    phase: mode === "final" ? "render_final" : "render_preview",
    progress: Math.max(Number(project.value?.progress || 0), 65),
  };
  startStatusPolling();
  if (!silent) {
    ElMessage.success(mode === "final" ? "开始导出MP4" : "开始生成预览");
  }
}

async function oneClickRoughCut() {
  if (!roughCutEnabled.value) {
    const minimum = Number(project.value?.minimumMatchPercent || 0);
    if (minimum < 80) {
      await ElMessageBox.alert(
        "上传视频与文案匹配度必须超过95%才能进行混剪。",
        "匹配度不足",
        { type: "warning" }
      ).catch(() => {});
    } else {
      ElMessage.warning(roughCutEnabledReason.value || "匹配率需达到95%后才可开始混剪");
    }
    return;
  }
  loading.oneClick = true;
  try {
    if (!sentences.value.length) {
      await splitScript(true);
    }
    await applySettings(true);
    await assignRoles(true);
    await buildTimelineOnly(true);
    await startExport("preview", true);
    ElMessage.success("一键混剪已启动");
  } catch (error) {
    ElMessage.error(error.message || "一键混剪失败");
  } finally {
    loading.oneClick = false;
  }
}

async function regenerateAll() {
  loading.regenerate = true;
  try {
    await applySettings(true);
    await assignRoles(true);
    await buildTimelineOnly(true);
    await startExport("preview", true);
    ElMessage.success("已重新生成混剪预览");
  } catch (error) {
    ElMessage.error(error.message || "重新生成失败");
  } finally {
    loading.regenerate = false;
  }
}

async function exportFinal() {
  loading.exportFinal = true;
  try {
    await syncAllSentencesBeforeRender();
    if (!timeline.value.length) {
      await buildTimelineOnly(true);
    }
    await startExport("final", true);
    ElMessage.success("MP4导出任务已启动");
  } catch (error) {
    ElMessage.error(error.message || "导出失败");
  } finally {
    loading.exportFinal = false;
  }
}

async function saveSentence(sentence) {
  sentenceLoading[sentence.id] = "save";
  try {
    const current = await ensureProject();
    project.value = await updateRoughCutSentence(current.id, sentence.id, {
      roleId: sentence.roleId || null,
      estimatedDuration: Number(sentence.estimatedDuration || 0),
      locked: !!sentence.locked,
    });
    ElMessage.success(`句子 #${sentence.index} 已保存`);
  } catch (error) {
    ElMessage.error(error.message || "保存句子失败");
  } finally {
    sentenceLoading[sentence.id] = "";
  }
}

async function regenerateSentence(sentence) {
  sentenceLoading[sentence.id] = "regen";
  try {
    const current = await ensureProject();
    project.value = await updateRoughCutSentence(current.id, sentence.id, {
      roleId: sentence.roleId || null,
      estimatedDuration: Number(sentence.estimatedDuration || 0),
      locked: !!sentence.locked,
    });
    project.value = await regenerateRoughCutSentence(current.id, sentence.id);
    await startExport("preview", true);
    ElMessage.success(`句子 #${sentence.index} 已重生并刷新预览`);
  } catch (error) {
    ElMessage.error(error.message || "单句重生失败");
  } finally {
    sentenceLoading[sentence.id] = "";
  }
}

function updateRoleUpload(roleId, files) {
  roleUploadFiles[roleId] = files || [];
}

async function uploadRoleAssets(roleId) {
  const files = roleUploadFiles[roleId] || [];
  if (!files.length || !files[0]) {
    ElMessage.warning(`请先选择角色 ${roleId} 的素材文件`);
    return;
  }
  uploadLoading[roleId] = true;
  try {
    const current = await ensureProject();
    project.value = await uploadRoughCutAssets(current.id, roleId, [files[0]]);
    roleUploadFiles[roleId] = [];
    startStatusPolling();
    ElMessage.success(`角色 ${roleId} 素材上传完成，已开始识别字幕`);
  } catch (error) {
    ElMessage.error(error.message || "素材上传失败");
  } finally {
    uploadLoading[roleId] = false;
  }
}

function previewAsset(asset) {
  if (!project.value?.id || !asset?.id) return;
  assetPreview.title = `预览：${asset.fileName || asset.id}`;
  assetPreview.url = getRoughCutAssetMediaUrl(project.value.id, asset.id);
  assetPreview.visible = true;
}

async function removeAsset(asset) {
  if (!project.value?.id || !asset?.id) return;
  try {
    await ElMessageBox.confirm(
      `确认删除素材 ${asset.fileName || asset.id}？`,
      "删除确认",
      { type: "warning" }
    );
  } catch (_error) {
    return;
  }

  assetActionLoading[asset.id] = "remove";
  try {
    project.value = await deleteRoughCutAsset(project.value.id, asset.id);
    ElMessage.success("素材已删除");
  } catch (error) {
    ElMessage.error(error.message || "删除素材失败");
  } finally {
    assetActionLoading[asset.id] = "";
  }
}

function startStatusPolling() {
  if (statusPollTimer.value || !project.value?.id) return;
  let previousStatus = project.value?.status || "";
  statusPollTimer.value = setInterval(async () => {
    if (!project.value?.id) {
      stopStatusPolling();
      return;
    }
    try {
      const latest = await getRoughCutProject(project.value.id);
      project.value = latest;
      const cachedCompare = compareCache[latest.id];
      upsertCompareProject({
        projectId: latest.id,
        projectTitle: latest.title || `项目#${latest.id}`,
        roles: cachedCompare?.roles || [],
        _loaded: !!cachedCompare?._loaded,
      }, !!cachedCompare?._loaded);
      await handleAsrCompletionAutoPopup(latest);

      if (previousStatus === "processing" && latest.status === "ready") {
        ElMessage.success("混剪任务处理完成");
      }
      if (previousStatus === "processing" && latest.status === "error") {
        ElMessage.error(latest.error || "混剪任务失败");
      }
      previousStatus = latest.status;

      const shouldKeep =
        latest.status === "processing" ||
        (Array.isArray(latest.rolesAsrProgress) &&
          latest.rolesAsrProgress.some((item) =>
            ["pending", "running"].includes(String(item?.status || "").toLowerCase())
          ));
      if (!shouldKeep) {
        stopStatusPolling();
      }
    } catch (_error) {
      stopStatusPolling();
    }
  }, 2000);
}

function stopStatusPolling() {
  if (!statusPollTimer.value) return;
  clearInterval(statusPollTimer.value);
  statusPollTimer.value = null;
}

async function onProjectChange(projectId) {
  if (!projectId) return;
  await loadProject(projectId);
}

async function refreshPreview() {
  if (!project.value?.id) return;
  await loadProject(project.value.id);
}

function downloadOutput() {
  if (!project.value?.outputUrl) return;
  window.open(project.value.outputUrl, "_blank");
}
</script>

<style scoped>
.loading-dots {
  display: inline-flex;
  gap: 0.4rem;
}

.loading-dots span {
  width: 0.7rem;
  height: 0.7rem;
  border-radius: 9999px;
  background: #ffffff;
  opacity: 0.35;
  animation: loading-dot-breathe 1.1s ease-in-out infinite;
}

.loading-dots span:nth-child(2) {
  animation-delay: 0.15s;
}

.loading-dots span:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes loading-dot-breathe {
  0%,
  80%,
  100% {
    transform: translateY(0);
    opacity: 0.35;
  }
  40% {
    transform: translateY(-4px);
    opacity: 1;
  }
}
</style>
