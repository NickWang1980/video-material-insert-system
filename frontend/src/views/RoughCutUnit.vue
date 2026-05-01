<template>
  <div class="space-y-6">
    <section class="workflow-node rounded-2xl border border-gray-200 bg-white p-5 shadow-card">
      <div class="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <div class="text-2xl font-bold tracking-tight">混剪单元</div>
          <p class="mt-2 text-sm text-gray-500">
            按工作流完成项目创建、角色素材识别、分镜生成、时间线同步与自动预览混剪。
          </p>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <el-button type="primary" @click="openCreateDialog">新建混剪项目</el-button>
        </div>
      </div>

      <div v-if="projects.length" class="mt-5 grid gap-3 md:grid-cols-2 2xl:grid-cols-3">
        <button
          v-for="item in projects"
          :key="item.id"
          type="button"
          class="rcu-project-card rounded-2xl border p-4 text-left transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg"
          :class="currentProjectId === item.id ? 'rcu-project-card--active border-black bg-black text-white' : 'border-gray-200 bg-gray-50 text-black'"
          @click="selectProject(item.id)"
        >
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <div class="truncate text-base font-semibold">{{ item.title }}</div>
              <div
                class="mt-1 truncate text-xs"
                :class="currentProjectId === item.id ? 'text-white/75' : 'text-gray-500'"
              >
                {{ item.scriptFileName || "未上传剧本 TXT" }}
              </div>
            </div>
            <el-tag size="small" :type="stageTagType(item.stageSummary)">
              {{ stageLabel(item.stageSummary) }}
            </el-tag>
          </div>
          <div
            class="mt-3 flex items-center gap-3 text-xs"
            :class="currentProjectId === item.id ? 'text-white/80' : 'text-gray-600'"
          >
            <span>角色 {{ item.roleCount || 0 }}</span>
            <span>素材 {{ item.assetCount || 0 }}</span>
            <span>进度 {{ Number(item.pipelineProgress || 0) }}%</span>
          </div>
          <div class="mt-3 flex items-center justify-between gap-2" @click.stop>
            <div>
              <el-button
                v-if="item.stageSummary === 'timeline_ready'"
                size="small"
                :loading="exportingStoryboardId === item.id"
                @click="handleCardExportStoryboard(item.id)"
              >
                导出时间线
              </el-button>
            </div>
            <div v-if="currentProjectId === item.id" class="flex items-center gap-1.5">
              <el-button size="small" @click="openRenameDialog">重命名</el-button>
              <el-button size="small" type="danger" plain @click="removeProject(project)">删除项目</el-button>
            </div>
          </div>
        </button>
      </div>
      <el-empty v-else class="mt-4" description="暂无混剪项目" />
      <el-pagination
        v-if="projectListTotal > projectListPageSize"
        class="mt-4 flex justify-end"
        background
        layout="sizes, prev, pager, next, total"
        :total="projectListTotal"
        :page-size="projectListPageSize"
        :page-sizes="[9, 18, 36]"
        :current-page="projectListPage"
        @size-change="handleProjectPageSizeChange"
        @current-change="handleProjectPageChange"
      />
    </section>

    <section
      v-if="project"
      class="workflow-node rounded-2xl border border-gray-200 bg-white p-5 shadow-card"
    >
      <div class="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div class="flex items-center gap-3">
            <span class="rounded-full bg-black px-3 py-1 text-xs font-semibold text-white">步骤 1</span>
            <h2 class="text-lg font-semibold">剧本文件上传卡片</h2>
          </div>
          <p class="mt-2 text-sm text-gray-500">
            上传带角色前缀的口播文案 TXT。格式必须包含 `A:`、`B:`、`C:` 这类角色行。
          </p>
        </div>
        <div class="flex flex-col gap-2">
          <div class="rounded-2xl border border-gray-200 bg-gray-50 px-4 py-2 text-sm">
            <div class="font-medium leading-snug">{{ project.title }}</div>
            <div class="mt-0.5 text-xs text-gray-500">{{ project.scriptFileName || "未绑定剧本文件" }}</div>
          </div>
          <div class="flex items-center gap-4 rounded-2xl border border-gray-200 bg-gray-50 px-4 py-2 text-xs text-gray-600">
            <span>角色数 <span class="ml-1 font-semibold text-gray-900">{{ roles.length }}</span></span>
            <span class="text-gray-300">|</span>
            <span>分镜数 <span class="ml-1 font-semibold text-gray-900">{{ sentences.length }}</span></span>
          </div>
        </div>
      </div>

      <div class="mt-5 grid gap-4 xl:grid-cols-[30%_70%]">
        <div class="rounded-2xl border border-dashed border-gray-300 bg-gray-50 p-4">
          <el-upload
            drag
            :auto-upload="false"
            :show-file-list="false"
            accept=".txt,text/plain"
            class="w-full"
            @change="onReplaceScriptFile"
          >
            <div class="py-8 text-center">
              <div class="text-base font-semibold">拖拽或选择新的剧本 TXT</div>
              <div class="mt-2 text-sm text-gray-500">上传后会重新识别角色、重建分镜头并清空旧预览</div>
            </div>
          </el-upload>
        </div>
        <div class="rounded-2xl border border-gray-200 bg-white p-4">
          <div class="flex items-center justify-between text-sm">
            <span class="font-medium">剧本状态</span>
            <el-tag :type="project.script ? 'success' : 'info'">
              {{ project.script ? "已识别角色" : "待上传" }}
            </el-tag>
          </div>
          <el-progress
            class="mt-4"
            :percentage="project.script ? 100 : 0"
            :stroke-width="14"
            :class="loading.script ? 'progress-breathing' : ''"
          />
          <div class="mt-4 max-h-48 overflow-auto rounded-xl border border-gray-200 bg-gray-50 p-3 text-sm leading-6 text-gray-700 whitespace-pre-wrap">
            {{ project.script || "上传后显示剧本文本预览。" }}
          </div>
        </div>
      </div>
    </section>

    <section
      v-if="project && roles.length"
      class="workflow-node rounded-2xl border border-gray-200 bg-white p-5 shadow-card"
    >
      <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div class="flex items-center gap-3">
            <span class="rounded-full bg-black px-3 py-1 text-xs font-semibold text-white">步骤 2</span>
            <h2 class="text-lg font-semibold">角色素材卡片节点</h2>
          </div>
          <p class="mt-2 text-sm text-gray-500">
            每个角色卡片独立接收视频素材。拖拽后自动上传、自动 ASR、自动计算匹配率。
          </p>
        </div>
        <div class="min-w-[260px] space-y-2">
          <div class="rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3">
            <div class="flex items-center justify-between text-sm font-medium">
              <span>角色识别总进度</span>
              <span>{{ roleStageProgress }}%</span>
            </div>
            <el-progress
              class="mt-3"
              :percentage="roleStageProgress"
              :stroke-width="14"
              :class="hasAsrRunning ? 'progress-breathing' : ''"
            />
            <div class="mt-3 text-xs text-gray-500">
              所有角色全部素材完成识别且通过门槛后，将自动生成时间线并开始预览版混剪。
            </div>
          </div>
          <div v-if="asrGlobalStatus.totalActive > 0" class="flex flex-wrap items-center gap-2 rounded-2xl border border-gray-200 bg-gray-50 px-4 py-2">
            <el-tag size="small" type="warning">
              ASR 识别中 {{ asrGlobalStatus.runningCount }}/{{ asrGlobalStatus.maxConcurrent }}
              <span v-if="asrGlobalStatus.queuedCount"> · 排队 {{ asrGlobalStatus.queuedCount }}</span>
            </el-tag>
            <span class="text-xs text-gray-400">
              模型：{{ asrGlobalStatus.loadedModels.length ? asrGlobalStatus.loadedModels.join(", ") : "加载中…" }}
            </span>
          </div>
        </div>
      </div>

      <div class="mt-5 grid gap-4 xl:grid-cols-2 2xl:grid-cols-3">
        <article
          v-for="role in roles"
          :key="role.id"
          class="rounded-2xl border border-gray-200 bg-gray-50 p-4 shadow-sm"
        >
          <div class="flex items-start justify-between gap-3">
            <div>
              <div class="text-lg font-semibold" :style="{ color: role.color || '#111827' }">
                {{ role.name || `角色 ${role.id}` }}
              </div>
              <div class="mt-1 text-xs text-gray-500">
                {{ roleStatusLabel(role.id) }} · 最低匹配率 {{ roleMatchPercent(role.id) }}%
              </div>
            </div>
            <el-tag size="small" :type="roleStatusTagType(role.id)">
              {{ roleAssetCount(role.id) }} 个素材
            </el-tag>
          </div>

          <el-progress
            class="mt-4"
            :percentage="roleProgressPercent(role.id)"
            :stroke-width="12"
            :class="roleIsRunning(role.id) ? 'progress-breathing' : ''"
          />

          <div
            class="mt-4 rounded-2xl border border-dashed p-3 transition-colors"
            :class="isRoleUploadLocked(role.id)
              ? 'border-gray-200 bg-gray-100 opacity-50 cursor-not-allowed'
              : 'border-gray-300 bg-white'"
          >
            <el-upload
              v-if="!isRoleUploadLocked(role.id)"
              drag
              :auto-upload="false"
              :multiple="false"
              :show-file-list="false"
              accept="video/*"
              class="w-full"
              @change="(file) => onRoleAssetSelected(role.id, file)"
            >
              <div class="py-3 text-center">
                <div class="text-sm font-semibold">拖拽或选择 {{ role.id }} 角色视频</div>
                <div class="mt-1 text-xs text-gray-500">选择后自动上传并开始异步 ASR 识别</div>
              </div>
            </el-upload>
            <div v-else class="py-3 text-center">
              <div class="text-sm font-semibold text-gray-400">等待角色 {{ prevRoleId(role.id) }} ASR 识别完成</div>
              <div class="mt-1 text-xs text-gray-400">上一角色 ASR 成功后自动解锁</div>
            </div>
          </div>

          <div class="mt-4 space-y-3" v-if="roleAssets(role.id).length">
            <div
              v-for="asset in roleAssets(role.id)"
              :key="asset.id"
              class="rounded-2xl border border-gray-200 bg-white p-3"
            >
              <div class="flex items-start justify-between gap-2">
                <div class="min-w-0">
                  <div class="truncate text-sm font-medium">{{ asset.fileName }}</div>
                  <div class="mt-1 text-xs text-gray-500">
                    {{ formatSeconds(asset.duration) }} · {{ asset.width }}x{{ asset.height }}
                  </div>
                  <div class="mt-1 flex items-center gap-1.5 text-xs">
                    <span
                      class="inline-block rounded-full px-1.5 py-0.5 font-medium"
                      :class="{
                        'bg-gray-100 text-gray-500': !asset.asrStatus || asset.asrStatus === 'pending',
                        'bg-blue-100 text-blue-600': asset.asrStatus === 'queued',
                        'bg-yellow-100 text-yellow-700': asset.asrStatus === 'running',
                        'bg-green-100 text-green-700': asset.asrStatus === 'completed',
                        'bg-red-100 text-red-600': asset.asrStatus === 'failed',
                      }"
                    >
                      {{ { pending: '等待', queued: '排队中', running: '识别中', completed: '已完成', failed: '失败' }[asset.asrStatus] || asset.asrStatus }}
                    </span>
                    <span class="text-gray-400">{{ Number(asset.asrProgress || 0) }}%</span>
                  </div>
                  <div class="mt-1 text-xs text-gray-500">
                    匹配率 {{ formatPercent(asset.matchPercent) }}% · 手动通过 {{ asset.manualGatePassed ? "是" : "否" }}
                  </div>
                </div>
                <el-tag size="small" :type="asset.gatePassed ? 'success' : 'warning'">
                  {{ asset.gatePassed ? "通过" : "待处理" }}
                </el-tag>
              </div>
              <el-progress
                class="mt-3"
                :percentage="Math.max(0, Math.min(100, Number(asset.asrProgress || 0)))"
                :stroke-width="8"
                :class="['pending', 'running'].includes(String(asset.asrStatus || '').toLowerCase()) ? 'progress-breathing' : ''"
              />
              <ExecutionMetaTags
                class="mt-2"
                :model="asset.asrModelUsed || ''"
                :compute="asset.asrComputeTypeUsed || ''"
              />
              <div class="mt-3 flex flex-wrap items-center gap-2">
                <el-button size="small" text @click="previewAsset(asset)">预览</el-button>
                <el-button size="small" text @click="openCompareDialog(role.id, asset.id)">匹配对比</el-button>
                <el-button
                  size="small"
                  text
                  type="danger"
                  :loading="assetActionLoading[asset.id] === 'remove'"
                  @click="removeAsset(asset)"
                >
                  删除
                </el-button>
              </div>
            </div>
          </div>
          <div v-else class="mt-4 rounded-2xl border border-dashed border-gray-200 bg-white px-3 py-5 text-center text-sm text-gray-500">
            当前角色还没有上传素材
          </div>
        </article>
      </div>
    </section>

    <section
      v-if="project && sentences.length"
      class="workflow-node rounded-2xl border border-gray-200 bg-white p-5 shadow-card"
    >
      <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div class="flex flex-wrap items-center gap-3">
            <span class="rounded-full bg-black px-3 py-1 text-xs font-semibold text-white">步骤 3 / 4</span>
            <h2 class="text-lg font-semibold">分镜头列表（句子卡片）</h2>
            <el-button
              size="small"
              :loading="loading.exportStoryboard"
              :disabled="!timeline.length"
              @click="handleExportStoryboard"
            >
              导出分镜时序
            </el-button>
            <el-button
              size="small"
              :loading="loading.importStoryboard"
              @click="triggerStoryboardImport"
            >
              导入分镜时序
            </el-button>
            <input
              ref="storyboardImportInputRef"
              type="file"
              accept=".json,application/json"
              style="display:none"
              @change="handleStoryboardImportFile"
            />
          </div>
          <p class="mt-2 text-sm text-gray-500">
            分镜头由剧本文案自动拆出，时长由匹配到的角色视频 ASR 片段决定；可折叠查看并逐句调整。
          </p>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <el-button text size="small" @click="storyboardCollapsed = !storyboardCollapsed">
            {{ storyboardCollapsed ? "展开" : "折叠" }}
          </el-button>
          <div class="min-w-[180px]">
            <el-progress
              :percentage="storyboardProgress"
              :stroke-width="12"
              :class="storyboardLoading ? 'progress-breathing' : ''"
            />
          </div>
        </div>
      </div>

      <div v-show="!storyboardCollapsed" class="mt-5 grid gap-3 2xl:grid-cols-2">
        <article
          v-for="sentence in sentences"
          :key="sentence.id"
          class="rounded-2xl border border-gray-200 p-4 shadow-sm"
          :style="{ backgroundColor: sentenceCardBg(sentence.roleId) }"
        >
          <div class="flex items-start justify-between gap-3">
            <div class="flex items-center gap-2 text-xs text-gray-500">
              <span class="rounded-full bg-white px-2 py-1 font-medium">#{{ sentence.index }}</span>
              <el-tag size="small" :style="{ backgroundColor: roleColor(sentence.roleId), color: '#fff', border: 'none' }">
                {{ sentence.roleId || "未分配" }}
              </el-tag>
            </div>
            <el-button size="small" text @click="openCompareDialog(sentence.roleId || '')">ASR匹配对比中心</el-button>
          </div>

          <div class="mt-3 whitespace-pre-wrap break-words text-sm leading-6 text-gray-800">
            {{ sentence.text }}
          </div>

          <div class="mt-4 grid gap-3 md:grid-cols-[140px_minmax(0,1fr)]">
            <el-input-number
              v-model="sentence.estimatedDuration"
              :min="0.8"
              :step="0.1"
              :precision="1"
              controls-position="right"
              size="small"
            />
            <div class="flex flex-col gap-1 rounded-xl border border-gray-200 bg-white px-3 py-2 text-xs text-gray-500">
              <div class="flex items-center justify-between gap-3">
                <span>{{ sentenceClip(sentence.id) ? "取材区间（可编辑）" : "尚未生成取材区间" }}</span>
                <el-switch v-model="sentence.locked" size="small" active-text="锁定时长" inactive-text="自动时长" />
              </div>
              <div v-if="sentenceClip(sentence.id)" class="mt-1 flex flex-wrap items-center gap-1">
                <el-input-number
                  v-model="getSentenceEdit(sentence.id).sourceStart"
                  size="small"
                  :precision="1"
                  :step="0.1"
                  :min="0"
                  style="width: 90px"
                />
                <span class="text-gray-400">-</span>
                <el-input-number
                  v-model="getSentenceEdit(sentence.id).sourceEnd"
                  size="small"
                  :precision="1"
                  :step="0.1"
                  :min="0"
                  style="width: 90px"
                />
                <span class="text-gray-400">秒</span>
                <span class="ml-2 text-gray-400">
                  ｜ 时间线 {{ formatSeconds(sentenceClip(sentence.id).timelineStart) }} - {{ formatSeconds(sentenceClip(sentence.id).timelineEnd) }}
                </span>
              </div>
            </div>
          </div>

          <div class="mt-3 flex flex-wrap items-center gap-2">
            <el-button
              size="small"
              :loading="sentenceLoading[sentence.id] === 'save'"
              @click="saveSentence(sentence)"
            >
              保存本句
            </el-button>
            <el-button
              size="small"
              :loading="sentencePreviewLoading[sentence.id]"
              :disabled="!sentenceClip(sentence.id)"
              @click="previewSentence(sentence)"
            >
              预览本句
            </el-button>
            <el-button
              size="small"
              text
              :loading="sentenceLoading[sentence.id] === 'regen'"
              @click="regenerateSentence(sentence)"
            >
              重生本句预览
            </el-button>
          </div>

          <div v-if="sentencePreviewUrls[sentence.id]" class="mt-3">
            <video
              :src="sentencePreviewUrls[sentence.id]"
              controls
              playsinline
              class="w-full rounded-xl"
              style="max-height: 280px; background: #000"
            />
          </div>
        </article>
      </div>
    </section>

    <section
      v-if="project && shouldShowTimelineSection"
      class="workflow-node rounded-2xl border border-gray-200 bg-white p-5 shadow-card"
    >
      <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div class="flex items-center gap-3">
            <span class="rounded-full bg-black px-3 py-1 text-xs font-semibold text-white">步骤 5 / 6 / 7</span>
            <h2 class="text-lg font-semibold">时间线与预览区域</h2>
          </div>
          <p class="mt-2 text-sm text-gray-500">
            时间线与播放器保持同步拖拽。系统会在素材达标后自动准备分镜与时间线，预览视频需要你手动点击按钮生成。
          </p>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <el-button :loading="loading.regenerate" :disabled="!project" @click="regeneratePreview">
            {{ previewActionLabel }}
          </el-button>
          <el-button
            type="warning"
            plain
            :loading="loading.stopPreview"
            :disabled="!project || project.status !== 'processing'"
            @click="stopPreviewGeneration"
          >
            停止生成预览
          </el-button>
          <el-button
            type="primary"
            :loading="loading.exportFinal"
            :disabled="!project || !project.previewUrl"
            @click="exportFinal"
          >
            导出视频
          </el-button>
          <el-tag :type="ffmpegStatus === 'blocked' ? 'danger' : 'success'">
            FFmpeg {{ ffmpegStatus === 'blocked' ? '阻塞' : '通畅' }}
            <span v-if="ffmpegRunningCount">· {{ ffmpegRunningCount }} 个进程</span>
          </el-tag>
          <el-button
            v-if="ffmpegStatus === 'blocked'"
            type="danger"
            plain
            :loading="ffmpegClearing"
            @click="clearFfmpegBlockedProcesses"
          >
            疏通 FFmpeg
          </el-button>
        </div>
      </div>

      <div class="mt-5 space-y-5">
        <div>
          <div class="mb-2 flex items-center justify-between text-sm">
            <span class="font-medium">混剪进度</span>
            <span>{{ pipelineProgress }}%</span>
          </div>
          <el-progress
            :percentage="pipelineProgress"
            :stroke-width="16"
            :class="project.status === 'processing' ? 'progress-breathing' : ''"
          />
        </div>

        <div class="grid gap-5 xl:grid-cols-[minmax(0,1.25fr)_minmax(360px,0.95fr)]">
          <div class="rcu-player-shell rounded-2xl border border-gray-200 bg-black p-3 text-white">
            <div class="mb-3 flex items-center justify-between text-sm">
              <div class="flex items-center gap-3">
                <span>预览播放器</span>
                <ExecutionMetaTags
                  :model="project?.asrModelUsed || ''"
                  :compute="project?.asrComputeTypeUsed || ''"
                  :encoder="project?.videoEncoderUsed || ''"
                  :resolution="project?.videoResolutionUsed || ''"
                />
              </div>
              <span>{{ previewStatusText }}</span>
            </div>
            <div
              class="rcu-player-inner relative overflow-hidden rounded-2xl border border-white/10 bg-black"
              :class="allAsrCompleted ? 'h-[36vh]' : 'h-[72vh]'"
            >
              <video
                v-if="currentMediaUrl"
                :key="currentMediaUrl"
                ref="videoRef"
                :src="currentMediaUrl"
                controls
                preload="metadata"
                class="h-full w-full bg-black object-contain"
                @timeupdate="onVideoTimeUpdate"
                @loadedmetadata="onVideoLoadedMetadata"
              />
              <div v-else class="h-full w-full bg-black" />

              <div
                v-if="previewBusy"
                class="absolute inset-0 flex flex-col items-center justify-center bg-black/60 text-white backdrop-blur-sm"
              >
                <div class="loading-dots">
                  <span />
                  <span />
                  <span />
                </div>
                <div class="mt-4 text-sm">正在自动生成预览视频</div>
              </div>
            </div>
          </div>

          <div class="space-y-5">
            <div class="rounded-2xl border border-gray-200 bg-gray-50 p-4">
              <div class="flex items-center justify-between text-sm font-medium">
                <span>时间线</span>
                <span>{{ formatSeconds(totalTimelineSeconds) }}</span>
              </div>

              <div v-if="timeline.length" class="mt-4 space-y-3">
                <div class="flex h-8 overflow-hidden rounded-xl border border-gray-200 bg-white">
                  <button
                    v-for="clip in timeline"
                    :key="clip.id"
                    type="button"
                    class="h-full transition hover:brightness-110"
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
                  当前时间 {{ formatSeconds(timelineSliderTime) }} / 总时长 {{ formatSeconds(totalTimelineSeconds) }}
                </div>
              </div>
              <div v-else class="mt-4 rounded-xl border border-dashed border-gray-300 bg-white px-3 py-6 text-center text-sm text-gray-500">
                自动时间线尚未生成，等待角色素材完成 ASR 或点击“重新生成预览”。
              </div>
            </div>

            <div class="rounded-2xl border border-gray-200 bg-gray-50 p-4">
              <div class="flex items-center justify-between text-sm font-medium">
                <span>日志与状态</span>
                <el-tag :type="statusTagType">{{ statusText }}</el-tag>
              </div>
              <div class="mt-3 text-xs text-gray-500">阶段：{{ stageLabel(project.stageSummary || project.phase) }}</div>
              <el-input
                class="mt-3"
                type="textarea"
                :rows="12"
                readonly
                :model-value="project.log || '暂无日志'"
              />
            </div>
          </div>
        </div>
      </div>
    </section>

    <el-dialog v-model="createDialog.visible" title="新建混剪项目" width="720px" destroy-on-close>
      <div class="space-y-4">
        <el-input v-model="createDialog.title" placeholder="项目名称（可选）" />
        <el-upload
          drag
          :auto-upload="false"
          :show-file-list="false"
          accept=".txt,text/plain"
          class="w-full"
          @change="onCreateScriptFileChange"
        >
          <div class="py-8 text-center">
            <div class="text-base font-semibold">拖拽或选择剧本 TXT</div>
            <div class="mt-2 text-sm text-gray-500">前端会读取文本并提交后端校验角色结构</div>
          </div>
        </el-upload>
        <div class="rounded-xl border border-gray-200 bg-gray-50 p-3 text-sm">
          <div class="font-medium">已选文件：{{ createDialog.scriptFileName || "未选择" }}</div>
          <div class="mt-2 max-h-48 overflow-auto whitespace-pre-wrap break-words text-gray-600">
            {{ createDialog.scriptPreview || "选择 TXT 后显示文本预览。" }}
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="createDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="loading.createProject" :disabled="!createDialog.script" @click="submitCreateProject">
          创建项目
        </el-button>
      </template>
    </el-dialog>

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
        class="w-full max-h-[70vh] rounded-xl"
      />
    </el-dialog>

    <el-dialog
      v-model="compareDialog.visible"
      title="ASR匹配对比中心"
      width="92vw"
      top="4vh"
      destroy-on-close
      align-center
    >
      <div v-if="compareDialog.loading" class="py-12 text-center text-sm text-gray-500">
        正在加载对比数据...
      </div>
      <div v-else-if="compareDialog.data">
        <div class="mb-3 flex flex-wrap items-center justify-between gap-3 text-xs text-gray-600">
          <span>当前项目：{{ compareDialog.data.projectTitle }}</span>
          <span v-if="currentCompareRole">
            角色 {{ currentCompareRole.roleId }} · 匹配率 {{ formatPercent(currentCompareRole.matchPercent) }}% ·
            {{ currentCompareRole.gatePassed ? "已通过" : "未通过" }}
          </span>
        </div>

        <el-tabs v-model="compareDialog.activeRoleId" class="compare-tabs">
          <el-tab-pane
            v-for="role in compareDialog.data.roles"
            :key="role.roleId"
            :label="`${role.roleId} (${formatPercent(role.matchPercent)}%)`"
            :name="role.roleId"
          >
            <el-tabs v-model="compareDialog.activeAssetId" type="card">
              <el-tab-pane
                v-for="asset in role.assets"
                :key="asset.assetId"
                :label="asset.fileName"
                :name="asset.assetId"
              >
                <div class="grid gap-4 xl:grid-cols-2">
                  <div class="rounded-2xl border border-gray-200 bg-gray-50 p-4">
                    <div class="mb-2 text-xs font-semibold text-gray-700">剧本文本（当前角色）</div>
                    <div class="max-h-[46vh] overflow-auto whitespace-pre-wrap break-words text-sm leading-6">
                      {{ role.mainText || "暂无角色文本" }}
                    </div>
                  </div>
                  <div class="rounded-2xl border border-gray-200 bg-gray-50 p-4">
                    <div class="mb-2 flex items-center justify-between gap-3">
                      <span class="text-xs font-semibold text-gray-700">ASR 文本（当前素材）</span>
                      <el-button size="small" text @click="refreshCompareData">刷新</el-button>
                    </div>
                    <div class="max-h-[46vh] overflow-auto whitespace-pre-wrap break-words text-sm leading-6">
                      {{ asset.asrText || "识别文本未同步，请刷新对比数据" }}
                    </div>
                  </div>
                </div>

                <div class="mt-4 grid gap-2 md:grid-cols-5 text-xs">
                  <div class="rounded-xl border border-gray-200 px-3 py-2">匹配字数 {{ asset.matchedChars }}</div>
                  <div class="rounded-xl border border-gray-200 px-3 py-2">总字数 {{ asset.srtTotalChars }}</div>
                  <div class="rounded-xl border border-gray-200 px-3 py-2">匹配率 {{ formatPercent(asset.matchPercent) }}%</div>
                  <div class="rounded-xl border border-gray-200 px-3 py-2">错误率 {{ formatPercent(asset.errorPercent) }}%</div>
                  <div class="rounded-xl border border-gray-200 px-3 py-2">ASR {{ asset.asrStatus }} · {{ asset.asrProgress }}%</div>
                </div>

                <div class="mt-4 flex flex-wrap items-center gap-2">
                  <el-switch
                    :model-value="!!asset.manualGatePassed"
                    active-text="手动通过"
                    inactive-text="未手动通过"
                    @change="(value) => updateManualGate(asset, value)"
                  />
                  <span class="text-xs text-gray-500">
                    手动通过可让当前素材在未达到门槛时仍参与自动混剪。
                  </span>
                </div>
                <div v-if="asset.asrError" class="mt-3 text-xs text-rose-600">错误：{{ asset.asrError }}</div>
              </el-tab-pane>
            </el-tabs>
          </el-tab-pane>
        </el-tabs>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import ExecutionMetaTags from "../components/common/ExecutionMetaTags.vue";

import {
  buildRoughCutTimeline,
  createRoughCutProject,
  deleteRoughCutAsset,
  deleteRoughCutProject,
  exportRoughCutProject,
  getRoughCutAssetMediaUrl,
  getRoughCutProject,
  getRoughCutProjectCompare,
  getRoughCutAsrStatus,
  getRoughCutFfmpegStatus,
  getRoughCutStatus,
  getRoughCutMediaUrl,
  listRoughCutProjects,
  clearRoughCutFfmpegBlocked,
  setRoughCutAssetManualGate,
  stopRoughCutProject,
  updateRoughCutProject,
  updateRoughCutSentence,
  regenerateRoughCutSentence,
  previewRoughCutSentence,
  getSentencePreviewUrl,
  uploadRoughCutAssets,
  exportRoughCutStoryboard,
  importRoughCutStoryboard,
} from "../api/roughCut";

const projects = ref([]);
const projectListPage = ref(1);
const projectListPageSize = ref(9);
const projectListTotal = ref(0);
const currentProjectId = ref(null);
const project = ref(null);
const timelineSliderTime = ref(0);
const isDraggingTimelineSlider = ref(false);
const selectedSentenceId = ref("");
const storyboardCollapsed = ref(false);
const videoRef = ref(null);
const statusTimer = ref(null);

const loading = reactive({
  createProject: false,
  script: false,
  regenerate: false,
  stopPreview: false,
  exportFinal: false,
  exportStoryboard: false,
  importStoryboard: false,
});

const sentenceLoading = reactive({});
const sentenceEdits = reactive({});
const sentencePreviewLoading = reactive({});
const sentencePreviewUrls = reactive({});
const assetActionLoading = reactive({});
const ffmpegStatus = ref("clear");
const ffmpegRunningCount = ref(0);
const asrGlobalStatus = ref({ runningCount: 0, queuedCount: 0, maxConcurrent: 2, totalActive: 0, loadedModels: [] });
const ffmpegBlockedProjectIds = ref([]);
const ffmpegLoading = ref(false);
const ffmpegClearing = ref(false);

const createDialog = reactive({
  visible: false,
  title: "",
  script: "",
  scriptFileName: "",
  scriptPreview: "",
});

const assetPreview = reactive({
  visible: false,
  title: "",
  url: "",
});

const compareDialog = reactive({
  visible: false,
  loading: false,
  data: null,
  activeRoleId: "",
  activeAssetId: "",
});

const roles = computed(() => project.value?.roles || []);
const assets = computed(() => project.value?.assets || []);
const sentences = computed(() => project.value?.sentences || []);
const timeline = computed(() => project.value?.timeline || []);

const totalTimelineSeconds = computed(() => {
  const last = timeline.value[timeline.value.length - 1];
  return last ? Number(last.timelineEnd || 0) : 0;
});

const pipelineProgress = computed(() => Number(project.value?.pipelineProgress || project.value?.progress || 0));
const hasAsrRunning = computed(() =>
  assets.value.some((item) => ["pending", "running"].includes(String(item.asrStatus || "").toLowerCase()))
);
const allAsrCompleted = computed(() =>
  assets.value.length > 0 && assets.value.every((a) => a.asrStatus === "completed")
);
const roleStageProgress = computed(() => {
  const rows = Array.isArray(project.value?.rolesAsrProgress) ? project.value.rolesAsrProgress : [];
  if (!rows.length) return roles.value.length ? 0 : 100;
  return Math.round(rows.reduce((sum, item) => sum + Number(item.progress || 0), 0) / rows.length);
});
const storyboardLoading = computed(() =>
  ["assign_roles", "build_timeline"].includes(String(project.value?.phase || "")) || project.value?.status === "processing"
);
const storyboardProgress = computed(() => {
  if (!sentences.value.length) return 0;
  if (timeline.value.length) return 100;
  if (storyboardLoading.value) return Math.max(10, pipelineProgress.value);
  return 35;
});
const shouldShowTimelineSection = computed(() => {
  const phase = String(project.value?.phase || "");
  return Boolean(
    timeline.value.length ||
      project.value?.previewUrl ||
      project.value?.outputUrl ||
      project.value?.status === "processing" ||
      ["assign_roles", "build_timeline", "render_preview", "completed"].includes(phase)
  );
});
const previewBusy = computed(
  () =>
    !!(
      loading.regenerate ||
      loading.exportFinal ||
      project.value?.status === "processing"
    )
);
const currentMediaUrl = computed(() => {
  if (!project.value?.id || previewBusy.value) return "";
  const mediaType = project.value?.previewUrl ? "preview" : project.value?.outputUrl ? "output" : "";
  if (!mediaType) return "";
  const base = getRoughCutMediaUrl(project.value.id, mediaType);
  const stamp = encodeURIComponent(
    `${project.value?.updatedAt || ""}_${project.value?.status || ""}_${project.value?.progress || 0}`
  );
  return `${base}&v=${stamp}`;
});
const statusText = computed(() => {
  if (!project.value) return "未选择项目";
  if (project.value.phase === "stopping") return "停止中";
  if (project.value.phase === "stopped") return "已停止";
  if (project.value.status === "processing") return "处理中";
  if (project.value.status === "ready") return "已就绪";
  if (project.value.status === "error") return "失败";
  return "待处理";
});
const statusTagType = computed(() => {
  if (project.value?.phase === "stopped") return "warning";
  if (project.value?.status === "ready") return "success";
  if (project.value?.status === "error") return "danger";
  if (project.value?.status === "processing") return "warning";
  return "info";
});
const previewActionLabel = computed(() => {
  if (!project.value?.previewUrl) return "生成预览视频";
  return "重新生成预览";
});
const previewStatusText = computed(() => {
  if (!project.value) return "未选择项目";
  if (project.value.phase === "stopping") return "正在停止生成";
  if (project.value.phase === "stopped") return "预览生成已停止";
  if (project.value.status === "processing") return "正在生成预览";
  if (project.value.previewUrl) return "预览已生成";
  if (timeline.value.length) return "时间线已就绪，点击生成预览";
  return "等待时间线生成";
});
const currentCompareRole = computed(() =>
  (compareDialog.data?.roles || []).find((item) => item.roleId === compareDialog.activeRoleId) || null
);

function openCreateDialog() {
  createDialog.visible = true;
  createDialog.title = nowProjectTitle();
  createDialog.script = "";
  createDialog.scriptFileName = "";
  createDialog.scriptPreview = "";
}

async function readTextFile(rawFile) {
  const buffer = await rawFile.arrayBuffer();
  const utf8 = new TextDecoder("utf-8").decode(buffer);
  if (!utf8.includes("�")) return utf8;
  try {
    return new TextDecoder("gb18030").decode(buffer);
  } catch {
    return utf8;
  }
}

async function onCreateScriptFileChange(file) {
  if (!file?.raw) return;
  try {
    const text = await readTextFile(file.raw);
    createDialog.script = text;
    createDialog.scriptPreview = text;
    createDialog.scriptFileName = file.raw.name || file.name || "";
  } catch (error) {
    ElMessage.error(error.message || "读取剧本文件失败");
  }
}

async function onReplaceScriptFile(file) {
  if (!project.value?.id || !file?.raw) return;
  loading.script = true;
  try {
    const text = await readTextFile(file.raw);
    const updated = await updateRoughCutProject(project.value.id, {
      script: text,
      scriptFileName: file.raw.name || file.name || "",
    });
    await refreshProjectList(updated.id);
    project.value = updated;
    syncAfterProjectUpdate();
    startStatusPolling();
    ElMessage.success("剧本已更新");
  } catch (error) {
    ElMessage.error(error.message || "更新剧本失败");
  } finally {
    loading.script = false;
  }
}

async function submitCreateProject() {
  loading.createProject = true;
  try {
    const created = await createRoughCutProject({
      title: createDialog.title || nowProjectTitle(),
      script: createDialog.script,
      scriptFileName: createDialog.scriptFileName || null,
    });
    createDialog.visible = false;
    projectListPage.value = 1;
    await refreshProjectList(created.id);
    project.value = created;
    currentProjectId.value = created.id;
    syncAfterProjectUpdate();
    startStatusPolling();
    ElMessage.success("混剪项目已创建");
  } catch (error) {
    ElMessage.error(error.message || "创建项目失败");
  } finally {
    loading.createProject = false;
  }
}

async function openRenameDialog() {
  if (!project.value) return;
  try {
    const { value } = await ElMessageBox.prompt("请输入新的项目名称", "重命名项目", {
      inputValue: project.value.title || "",
      confirmButtonText: "保存",
      cancelButtonText: "取消",
    });
    const updated = await updateRoughCutProject(project.value.id, { title: value });
    projectListPage.value = 1;
    await refreshProjectList(updated.id);
    project.value = updated;
    syncAfterProjectUpdate();
    ElMessage.success("项目名称已更新");
  } catch (error) {
    if (error === "cancel" || error === "close") return;
    ElMessage.error(error.message || "重命名失败");
  }
}

async function removeProject(targetProject) {
  if (!targetProject?.id) return;
  try {
    await ElMessageBox.confirm(`确认删除项目「${targetProject.title}」？`, "删除项目", {
      type: "warning",
      confirmButtonText: "删除",
      cancelButtonText: "取消",
    });
    await deleteRoughCutProject(targetProject.id);
    const isCurrent = currentProjectId.value === targetProject.id;
    projectListPage.value = 1;
    await refreshProjectList(isCurrent ? null : currentProjectId.value);
    if (isCurrent) {
      if (projects.value.length) {
        currentProjectId.value = projects.value[0].id;
        await loadProject(currentProjectId.value);
      } else {
        currentProjectId.value = null;
        project.value = null;
      }
    }
    ElMessage.success("项目已删除");
  } catch (error) {
    if (error === "cancel" || error === "close") return;
    ElMessage.error(error.message || "删除项目失败");
  }
}

async function refreshProjectList(preferredId = null) {
  const { items, total } = await listRoughCutProjects(projectListPage.value, projectListPageSize.value);
  projectListTotal.value = total;
  projects.value = items;
  if (!total) {
    currentProjectId.value = null;
    return;
  }
  const targetId = preferredId || currentProjectId.value;
  if (targetId && items.some((item) => item.id === targetId)) {
    currentProjectId.value = targetId;
  } else if (items.length) {
    currentProjectId.value = items[0].id;
  }
}

async function handleProjectPageChange(page) {
  projectListPage.value = page;
  await refreshProjectList();
}

async function handleProjectPageSizeChange(size) {
  projectListPageSize.value = size;
  projectListPage.value = 1;
  await refreshProjectList();
}

async function selectProject(projectId) {
  currentProjectId.value = projectId;
}

async function loadProject(projectId) {
  if (!projectId) return;
  project.value = await getRoughCutProject(projectId);
  syncAfterProjectUpdate();
  await Promise.all([refreshFfmpegStatus(), refreshAsrStatus()]);
  startStatusPolling();
}

function syncAfterProjectUpdate() {
  if (!project.value) return;
  if (!selectedSentenceId.value && sentences.value.length) {
    selectedSentenceId.value = sentences.value[0].id;
  }
  if (!timeline.value.length) {
    timelineSliderTime.value = 0;
  }
}

async function refreshFfmpegStatus() {
  ffmpegLoading.value = true;
  try {
    const result = await getRoughCutFfmpegStatus();
    ffmpegStatus.value = result?.status || "clear";
    ffmpegRunningCount.value = Number(result?.runningCount || 0);
    ffmpegBlockedProjectIds.value = result?.blockedProjectIds || [];
  } catch (error) {
    ffmpegStatus.value = "clear";
  } finally {
    ffmpegLoading.value = false;
  }
}

async function refreshAsrStatus() {
  try {
    const result = await getRoughCutAsrStatus();
    asrGlobalStatus.value = result || asrGlobalStatus.value;
  } catch {
    // silently ignore
  }
}

async function clearFfmpegBlockedProcesses() {
  if (ffmpegClearing.value) return;
  ffmpegClearing.value = true;
  try {
    await clearRoughCutFfmpegBlocked();
    ElMessage.success("FFmpeg 进程已疏通");
    await refreshFfmpegStatus();
    await pollProjectStatus();
  } catch (error) {
    ElMessage.error(error.message || "疏通 FFmpeg 失败");
  } finally {
    ffmpegClearing.value = false;
  }
}

function roleAssets(roleId) {
  return assets.value.filter((item) => item.roleId === roleId);
}

function isRoleUploadLocked(roleId) {
  const idx = roles.value.findIndex((r) => r.id === roleId);
  if (idx <= 0) return false;
  const prevId = roles.value[idx - 1].id;
  // Locked until the previous role has at least one asset that completed ASR
  return !roleAssets(prevId).some((a) => a.asrStatus === "completed");
}

function prevRoleId(roleId) {
  const idx = roles.value.findIndex((r) => r.id === roleId);
  return idx > 0 ? roles.value[idx - 1].id : null;
}

function roleProgressItem(roleId) {
  return (project.value?.rolesAsrProgress || []).find((item) => item.roleId === roleId) || null;
}

function roleStatusLabel(roleId) {
  const row = roleProgressItem(roleId);
  const status = String(row?.status || "").toLowerCase();
  if (status === "completed") return "识别完成";
  if (status === "running") return "识别中";
  if (status === "pending") return "等待识别";
  if (status === "missing") return "待上传素材";
  if (status === "failed") return "识别失败";
  return "待处理";
}

function roleStatusTagType(roleId) {
  const status = String(roleProgressItem(roleId)?.status || "").toLowerCase();
  if (status === "completed") return "success";
  if (status === "failed") return "danger";
  if (status === "running" || status === "pending") return "warning";
  return "info";
}

function roleAssetCount(roleId) {
  return roleAssets(roleId).length;
}

function roleProgressPercent(roleId) {
  return Number(roleProgressItem(roleId)?.progress || 0);
}

function roleMatchPercent(roleId) {
  return formatPercent(roleProgressItem(roleId)?.matchPercent || 0);
}

function roleIsRunning(roleId) {
  const status = String(roleProgressItem(roleId)?.status || "").toLowerCase();
  return status === "running" || status === "pending";
}

function roleColor(roleId) {
  return roles.value.find((item) => item.id === roleId)?.color || "#111827";
}

// ── Sentence card background palette (3 themes × 8 hues) ──────────────────
const _SENTENCE_BG_PALETTES = {
  light: [
    "#ede9fe", // violet
    "#dbeafe", // sky blue
    "#d1fae5", // mint green
    "#fce7f3", // rose
    "#fef3c7", // amber
    "#cffafe", // cyan
    "#e0e7ff", // indigo
    "#fee2e2", // blush red
  ],
  dark: [
    "#2d1f5e", // deep violet
    "#1e3a5f", // deep navy blue
    "#1a3a2e", // deep forest green
    "#3d1a2e", // deep wine rose
    "#3d2e0e", // deep amber
    "#0e3040", // deep teal
    "#1e1a4a", // deep indigo
    "#3d1a1a", // deep crimson
  ],
  glass: [
    "rgba(139, 92, 246, 0.22)",  // violet glass
    "rgba(59, 130, 246, 0.20)",  // blue glass
    "rgba(16, 185, 129, 0.18)",  // emerald glass
    "rgba(236, 72, 153, 0.18)",  // pink glass
    "rgba(245, 158, 11, 0.18)",  // amber glass
    "rgba(6, 182, 212, 0.18)",   // cyan glass
    "rgba(99, 102, 241, 0.22)",  // indigo glass
    "rgba(239, 68, 68, 0.18)",   // red glass
  ],
};

// Reactive theme detection — mirrors App.vue's html class changes
const _currentTheme = ref(
  document.documentElement.classList.contains("glass")
    ? "glass"
    : document.documentElement.classList.contains("dark")
    ? "dark"
    : "light"
);
let _themeObserver = null;
onMounted(() => {
  _themeObserver = new MutationObserver(() => {
    const cl = document.documentElement.classList;
    _currentTheme.value = cl.contains("glass") ? "glass" : cl.contains("dark") ? "dark" : "light";
  });
  _themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
});
onBeforeUnmount(() => _themeObserver?.disconnect());

// Map each roleId to a stable hue index in order of first appearance
const _roleHueIndex = computed(() => {
  const map = {};
  roles.value.forEach((r, i) => { map[r.id] = i; });
  return map;
});

function sentenceCardBg(roleId) {
  const palette = _SENTENCE_BG_PALETTES[_currentTheme.value] ?? _SENTENCE_BG_PALETTES.light;
  const idx = _roleHueIndex.value[roleId] ?? 0;
  return palette[idx % palette.length];
}

async function onRoleAssetSelected(roleId, file) {
  if (!project.value?.id || !file?.raw) return;
  assetActionLoading[file.uid || `${roleId}_${Date.now()}`] = "upload";
  try {
    const updated = await uploadRoughCutAssets(project.value.id, roleId, [file.raw]);
    project.value = updated;
    syncAfterProjectUpdate();
    startStatusPolling();
    ElMessage.success(`角色 ${roleId} 素材已上传，正在进行 ASR 识别`);
  } catch (error) {
    ElMessage.error(error.message || "上传角色素材失败");
  } finally {
    assetActionLoading[file.uid || `${roleId}_${Date.now()}`] = "";
  }
}

function previewAsset(asset) {
  if (!project.value?.id || !asset?.id) return;
  assetPreview.title = asset.fileName || "素材预览";
  assetPreview.url = getRoughCutAssetMediaUrl(project.value.id, asset.id);
  assetPreview.visible = true;
}

async function removeAsset(asset) {
  if (!project.value?.id || !asset?.id) return;
  assetActionLoading[asset.id] = "remove";
  try {
    project.value = await deleteRoughCutAsset(project.value.id, asset.id);
    await refreshProjectList(project.value.id);
    syncAfterProjectUpdate();
    ElMessage.success("素材已删除");
  } catch (error) {
    ElMessage.error(error.message || "删除素材失败");
  } finally {
    assetActionLoading[asset.id] = "";
  }
}

async function syncAllSentencesBeforeRender() {
  if (!project.value?.id || !sentences.value.length) return;
  const draftSentences = sentences.value.map((sentence) => ({
    id: sentence.id,
    estimatedDuration: Number(sentence.estimatedDuration || 0),
    locked: !!sentence.locked,
  }));

  let latest = null;
  for (const draft of draftSentences) {
    latest = await updateRoughCutSentence(project.value.id, draft.id, {
      estimatedDuration: draft.estimatedDuration,
      locked: draft.locked,
    });
  }
  if (latest) {
    project.value = latest;
    syncAfterProjectUpdate();
  }
}

async function saveSentence(sentence) {
  if (!project.value?.id) return;
  sentenceLoading[sentence.id] = "save";
  try {
    const edit = sentenceEdits[sentence.id];
    const clip = sentenceClip(sentence.id);
    const payload = {
      estimatedDuration: Number(sentence.estimatedDuration || 0),
      locked: !!sentence.locked,
    };
    const hasOverride =
      edit &&
      clip &&
      (Math.abs(edit.sourceStart - clip.sourceStart) > 0.05 ||
        Math.abs(edit.sourceEnd - clip.sourceEnd) > 0.05);
    if (hasOverride) {
      payload.sourceStart = edit.sourceStart;
      payload.sourceEnd = edit.sourceEnd;
    }
    project.value = await updateRoughCutSentence(project.value.id, sentence.id, payload);
    syncAfterProjectUpdate();
    if (hasOverride) {
      project.value = await regenerateRoughCutSentence(project.value.id, sentence.id);
      syncAfterProjectUpdate();
      delete sentenceEdits[sentence.id];
      ElMessage.success(`分镜 #${sentence.index} 已保存并重新取材`);
    } else {
      ElMessage.success(`分镜 #${sentence.index} 已保存`);
    }
  } catch (error) {
    ElMessage.error(error.message || "保存分镜失败");
  } finally {
    sentenceLoading[sentence.id] = "";
  }
}

async function regenerateSentence(sentence) {
  if (!project.value?.id) return;
  sentenceLoading[sentence.id] = "regen";
  try {
    await saveSentence(sentence);
    await exportRoughCutProject(project.value.id, "preview");
    project.value = {
      ...project.value,
      status: "processing",
      phase: "render_preview",
      progress: Math.max(Number(project.value?.progress || 0), 65),
    };
    startStatusPolling();
    ElMessage.success(`分镜 #${sentence.index} 已开始重新生成预览`);
  } catch (error) {
    ElMessage.error(error.message || "重生分镜失败");
  } finally {
    sentenceLoading[sentence.id] = "";
  }
}

async function regeneratePreview() {
  if (!project.value?.id) return;
  loading.regenerate = true;
  try {
    const hasExistingPreview = Boolean(project.value?.previewUrl);
    await syncAllSentencesBeforeRender();
    project.value = await buildRoughCutTimeline(project.value.id, true);
    await exportRoughCutProject(project.value.id, "preview");
    project.value = {
      ...project.value,
      status: "processing",
      phase: "render_preview",
      progress: Math.max(Number(project.value?.progress || 0), 65),
    };
    startStatusPolling();
    ElMessage.success(hasExistingPreview ? "已开始重新生成预览" : "已开始生成预览视频");
  } catch (error) {
    ElMessage.error(error.message || "生成预览失败");
  } finally {
    loading.regenerate = false;
  }
}

async function stopPreviewGeneration() {
  if (!project.value?.id || project.value.status !== "processing") return;
  loading.stopPreview = true;
  try {
    project.value = await stopRoughCutProject(project.value.id);
    await refreshProjectList(project.value.id);
    startStatusPolling();
    ElMessage.success("已发送停止请求");
  } catch (error) {
    ElMessage.error(error.message || "停止生成预览失败");
  } finally {
    loading.stopPreview = false;
  }
}

const storyboardImportInputRef = ref(null);
const exportingStoryboardId = ref(null);

async function handleCardExportStoryboard(projectId) {
  exportingStoryboardId.value = projectId;
  try {
    await exportRoughCutStoryboard(projectId);
    ElMessage.success("分镜头时序已导出");
  } catch (e) {
    ElMessage.error(e.message || "导出失败");
  } finally {
    exportingStoryboardId.value = null;
  }
}

async function handleExportStoryboard() {
  if (!project.value?.id) return;
  loading.exportStoryboard = true;
  try {
    await exportRoughCutStoryboard(project.value.id);
    ElMessage.success("分镜头时序已导出");
  } catch (e) {
    ElMessage.error(e.message || "导出失败");
  } finally {
    loading.exportStoryboard = false;
  }
}

function triggerStoryboardImport() {
  if (!project.value?.id) return;
  storyboardImportInputRef.value?.click();
}

async function handleStoryboardImportFile(event) {
  const file = event.target.files?.[0];
  event.target.value = "";
  if (!file || !project.value?.id) return;
  try {
    await ElMessageBox.confirm(
      `确认将「${file.name}」导入到工程「${project.value.title}」？\n当前分镜时序将被覆盖。`,
      "导入分镜时序",
      { type: "warning", confirmButtonText: "确认导入", cancelButtonText: "取消" }
    );
  } catch {
    return;
  }

  loading.importStoryboard = true;
  try {
    project.value = await importRoughCutStoryboard(project.value.id, file);
    project.value = await buildRoughCutTimeline(project.value.id, true);
    syncAfterProjectUpdate();
    ElMessage.success("分镜时序已导入并重新取材");
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message || "导入失败");
  } finally {
    loading.importStoryboard = false;
  }
}

async function exportFinal() {
  if (!project.value?.id || !project.value?.previewUrl) return;
  loading.exportFinal = true;
  try {
    const token = localStorage.getItem("vmis_token") || "";
    const url = getRoughCutMediaUrl(project.value.id, "preview");
    const resp = await fetch(url, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!resp.ok) throw new Error("视频获取失败");
    const blob = await resp.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${project.value.title || "混剪视频"}.mp4`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(a.href);
    ElMessage.success("视频已开始下载");
  } catch (error) {
    ElMessage.error(error.message || "视频导出失败");
  } finally {
    loading.exportFinal = false;
  }
}

async function openCompareDialog(roleId = "", assetId = "") {
  if (!project.value?.id) return;
  compareDialog.visible = true;
  compareDialog.loading = true;
  compareDialog.activeRoleId = roleId || compareDialog.activeRoleId;
  compareDialog.activeAssetId = assetId || compareDialog.activeAssetId;
  try {
    await refreshCompareData();
  } catch (error) {
    ElMessage.error(error.message || "加载匹配对比失败");
  } finally {
    compareDialog.loading = false;
  }
}

async function refreshCompareData() {
  if (!project.value?.id) return;
  const data = await getRoughCutProjectCompare(project.value.id);
  compareDialog.data = data;
  const rolesInDialog = data?.roles || [];
  const defaultRoleId =
    rolesInDialog.some((item) => item.roleId === compareDialog.activeRoleId)
      ? compareDialog.activeRoleId
      : rolesInDialog[0]?.roleId || "";
  compareDialog.activeRoleId = defaultRoleId;
  const currentRole = rolesInDialog.find((item) => item.roleId === defaultRoleId) || rolesInDialog[0];
  const roleAssetsList = currentRole?.assets || [];
  compareDialog.activeAssetId =
    roleAssetsList.some((item) => item.assetId === compareDialog.activeAssetId)
      ? compareDialog.activeAssetId
      : compareDialog.activeAssetId || roleAssetsList[0]?.assetId || "";
}

async function updateManualGate(asset, manualPassed) {
  if (!project.value?.id || !asset?.assetId) return;
  try {
    project.value = await setRoughCutAssetManualGate(project.value.id, asset.assetId, manualPassed);
    await refreshProjectList(project.value.id);
    await refreshCompareData();
    syncAfterProjectUpdate();
    startStatusPolling();
    ElMessage.success("手动通过状态已更新");
  } catch (error) {
    ElMessage.error(error.message || "更新手动通过失败");
  }
}

function stageLabel(stage) {
  const map = {
    draft: "待上传剧本",
    script_invalid: "剧本无效",
    waiting_assets: "待上传角色素材",
    waiting_asr: "ASR识别中",
    waiting_gate: "待人工确认",
    script_ready: "待生成时间线",
    timeline_ready: "时间线已就绪",
    rendering: "生成预览中",
    stopping: "停止中",
    stopped: "已停止",
    error: "处理失败",
  };
  return map[String(stage || "").trim()] || "进行中";
}

function stageTagType(stage) {
  const value = String(stage || "").trim();
  if (value === "timeline_ready") return "success";
  if (value === "rendering" || value === "stopping" || value === "stopped") return "warning";
  if (value === "error" || value === "script_invalid") return "danger";
  return "info";
}

function formatSeconds(seconds) {
  const total = Math.max(0, Number(seconds || 0));
  const minutes = Math.floor(total / 60);
  const secs = Math.floor(total % 60);
  const ms = Math.floor((total - Math.floor(total)) * 10);
  return `${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}.${ms}`;
}

function formatPercent(value) {
  return Number(value || 0).toFixed(1);
}

function sentenceClip(sentenceId) {
  const sentence = sentences.value.find((item) => item.id === sentenceId);
  if (!sentence?.clipId) return null;
  return timeline.value.find((clip) => clip.id === sentence.clipId) || null;
}

function sentenceClipText(sentenceId) {
  const clip = sentenceClip(sentenceId);
  if (!clip) return "尚未生成取材区间";
  return `取材 ${formatSeconds(clip.sourceStart)} - ${formatSeconds(clip.sourceEnd)} ｜ 时间线 ${formatSeconds(
    clip.timelineStart
  )} - ${formatSeconds(clip.timelineEnd)}`;
}

function getSentenceEdit(sentenceId) {
  if (!sentenceEdits[sentenceId]) {
    const sentence = sentences.value.find((s) => s.id === sentenceId);
    const clip = sentenceClip(sentenceId);
    const start = sentence?.sourceStartOverride ?? clip?.sourceStart ?? 0;
    const end = sentence?.sourceEndOverride ?? clip?.sourceEnd ?? 0;
    sentenceEdits[sentenceId] = { sourceStart: Number(start), sourceEnd: Number(end) };
  }
  return sentenceEdits[sentenceId];
}

async function previewSentence(sentence) {
  if (!project.value?.id) return;
  sentencePreviewLoading[sentence.id] = true;
  delete sentencePreviewUrls[sentence.id];
  try {
    await previewRoughCutSentence(project.value.id, sentence.id);
    const _previewBase = getSentencePreviewUrl(project.value.id, sentence.id);
    sentencePreviewUrls[sentence.id] = _previewBase + (_previewBase.includes("?") ? "&" : "?") + `t=${Date.now()}`;
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || error.message || "单句预览生成失败");
  } finally {
    sentencePreviewLoading[sentence.id] = false;
  }
}

function timelineClipStyle(clip) {
  const total = Math.max(totalTimelineSeconds.value, 0.1);
  const width = ((Number(clip.duration || 0) / total) * 100).toFixed(2);
  return {
    width: `${Math.max(2, Number(width))}%`,
    background: roleColor(clip.roleId),
  };
}

function timelineTitle(clip) {
  return `${clip.roleId}｜${clip.subtitleText}`;
}

function selectSentenceFromTimeline(clip) {
  selectedSentenceId.value = clip.sentenceId;
  if (videoRef.value) {
    videoRef.value.currentTime = Number(clip.timelineStart || 0);
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

function shouldPollProject() {
  if (!project.value?.id) return false;
  if (project.value.status === "processing") return true;
  return assets.value.some((item) => ["pending", "queued", "running"].includes(String(item.asrStatus || "").toLowerCase()));
}

async function pollProjectStatus() {
  if (!project.value?.id) return;
  try {
    const latest = await getRoughCutProject(project.value.id);
    project.value = latest;
    syncAfterProjectUpdate();
    await Promise.all([refreshFfmpegStatus(), refreshAsrStatus()]);
    if (compareDialog.visible) {
      await refreshCompareData();
    }
    await refreshProjectList(project.value.id);
  } catch (error) {
    stopStatusPolling();
  }
}

function startStatusPolling() {
  stopStatusPolling();
  if (!shouldPollProject()) return;
  statusTimer.value = window.setInterval(() => {
    pollProjectStatus();
  }, 2500);
}

function stopStatusPolling() {
  if (!statusTimer.value) return;
  clearInterval(statusTimer.value);
  statusTimer.value = null;
}

function nowProjectTitle() {
  const date = new Date();
  const pad = (value) => String(value).padStart(2, "0");
  return `混剪项目_${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}_${pad(
    date.getHours()
  )}${pad(date.getMinutes())}${pad(date.getSeconds())}`;
}

watch(
  () => currentProjectId.value,
  async (value) => {
    if (!value) return;
    await loadProject(value);
  }
);

watch(
  () => compareDialog.activeRoleId,
  (roleId) => {
    if (!roleId) return;
    const role = (compareDialog.data?.roles || []).find((item) => item.roleId === roleId);
    if (!role) return;
    if (!role.assets.some((item) => item.assetId === compareDialog.activeAssetId)) {
      compareDialog.activeAssetId = role.assets[0]?.assetId || "";
    }
  }
);

onMounted(async () => {
  await refreshProjectList();
});

onBeforeUnmount(() => {
  stopStatusPolling();
});
</script>

<style scoped>
.workflow-node {
  animation: node-fade-in 1s ease both;
}

.progress-breathing :deep(.el-progress-bar__inner) {
  animation: progress-breathe 1.4s ease-in-out infinite;
  box-shadow: 0 0 0 1px rgba(17, 24, 39, 0.08), 0 0 18px rgba(59, 130, 246, 0.25);
}

.loading-dots {
  display: inline-flex;
  gap: 10px;
}

.loading-dots span {
  width: 12px;
  height: 12px;
  border-radius: 999px;
  background: white;
  animation: dot-bounce 1s infinite ease-in-out;
}

.loading-dots span:nth-child(2) {
  animation-delay: 0.12s;
}

.loading-dots span:nth-child(3) {
  animation-delay: 0.24s;
}

@keyframes node-fade-in {
  from {
    opacity: 0;
    transform: translateY(18px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes progress-breathe {
  0%,
  100% {
    opacity: 0.78;
    transform: scaleY(0.96);
  }
  50% {
    opacity: 1;
    transform: scaleY(1);
  }
}

@keyframes dot-bounce {
  0%,
  80%,
  100% {
    opacity: 0.35;
    transform: translateY(0);
  }
  40% {
    opacity: 1;
    transform: translateY(-6px);
  }
}

/* ─── Liquid Glass overrides ─────────────────────────────────────────────── */

:global(html.glass) .workflow-node {
  background: linear-gradient(
    135deg,
    rgba(255, 255, 255, 0.10) 0%,
    rgba(255, 255, 255, 0.04) 100%
  ) !important;
  border-color: rgba(255, 255, 255, 0.18) !important;
  backdrop-filter: blur(32px) saturate(160%);
  -webkit-backdrop-filter: blur(32px) saturate(160%);
  box-shadow:
    inset 0 1.5px 0 rgba(255, 255, 255, 0.22),
    inset 0 -1px 0 rgba(255, 255, 255, 0.06),
    0 8px 40px rgba(0, 0, 0, 0.28) !important;
}

/* Keep the video player shell dark in glass mode */
:global(html.glass) .rcu-player-shell {
  background: rgba(6, 6, 16, 0.72) !important;
  border-color: rgba(255, 255, 255, 0.12) !important;
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.10),
    0 4px 24px rgba(0, 0, 0, 0.40) !important;
}

/* Keep the inner video viewport pure black */
:global(html.glass) .rcu-player-inner {
  background: #000 !important;
  border-color: rgba(255, 255, 255, 0.08) !important;
}

/* ── Inactive project card: visible glass panel ── */
:global(html.glass) .rcu-project-card {
  background: rgba(255, 255, 255, 0.11) !important;
  border-color: rgba(255, 255, 255, 0.20) !important;
  backdrop-filter: blur(16px) saturate(150%);
  -webkit-backdrop-filter: blur(16px) saturate(150%);
  box-shadow:
    inset 0 1.5px 0 rgba(255, 255, 255, 0.22),
    inset 0 -1px 0 rgba(255, 255, 255, 0.06),
    0 2px 12px rgba(0, 0, 0, 0.18);
}
:global(html.glass) .rcu-project-card:hover {
  background: rgba(255, 255, 255, 0.17) !important;
  border-color: rgba(255, 255, 255, 0.34) !important;
  box-shadow:
    inset 0 1.5px 0 rgba(255, 255, 255, 0.30),
    0 6px 24px rgba(0, 0, 0, 0.24);
}

/* ── Active project card: prominent dark glass with purple accent ── */
:global(html.glass) .rcu-project-card--active,
:global(html.glass) .rcu-project-card.rcu-project-card--active {
  background: rgba(12, 8, 32, 0.86) !important;
  border-color: rgba(160, 130, 255, 0.55) !important;
  backdrop-filter: blur(20px) saturate(160%);
  -webkit-backdrop-filter: blur(20px) saturate(160%);
  box-shadow:
    inset 0 1.5px 0 rgba(200, 180, 255, 0.30),
    0 0 0 1px rgba(160, 130, 255, 0.22),
    0 6px 24px rgba(80, 40, 180, 0.28) !important;
  color: #fff !important;
}

/* Step-badge pills in glass mode */
:global(html.glass) .rounded-full.bg-black {
  background: rgba(10, 10, 24, 0.80) !important;
  border: 1px solid rgba(255, 255, 255, 0.16);
}

/* Dashed upload-zone borders */
:global(html.glass) .border-gray-300 {
  border-color: rgba(255, 255, 255, 0.22) !important;
}
</style>
