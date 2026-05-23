<template>
  <div class="space-y-3">
    <el-tabs v-model="activeTab" @tab-change="onTabChange">
      <el-tab-pane label="上传 mp4" name="upload">
        <el-upload
          drag
          :multiple="false"
          :auto-upload="false"
          :show-file-list="false"
          :on-change="onFileChange"
          accept=".mp4,.mov,.mkv,.avi,.webm"
        >
          <div class="p-6 text-center">
            <div class="text-3xl mb-1">🎬</div>
            <div class="text-sm text-gray-700">拖入参考视频，或点击选择</div>
            <div class="text-xs text-gray-400 mt-1">必须含一个正脸；&lt;1 GB；mp4/mov/mkv/avi/webm</div>
          </div>
        </el-upload>
        <div v-if="uploadFile" class="text-xs text-gray-600 mt-2 flex items-center gap-2">
          <span class="font-mono break-all">{{ uploadFile.name }}</span>
          <span>· {{ formatSize(uploadFile.size) }}</span>
          <el-button text type="danger" size="small" @click="clearUpload">移除</el-button>
        </div>
      </el-tab-pane>

      <el-tab-pane label="从原视频选" name="source">
        <div class="flex items-center gap-2 mb-2">
          <el-button size="small" :loading="sourcesLoading" @click="loadSources">刷新</el-button>
          <span class="text-xs text-gray-500">来自「原视频」库</span>
        </div>
        <el-table
          :data="sourceVideos"
          :height="280"
          highlight-current-row
          @current-change="onSourceRowSelect"
          v-loading="sourcesLoading"
        >
          <el-table-column label="名称" min-width="220">
            <template #default="{ row }">
              <div class="text-xs font-mono break-all">{{ row.name }}</div>
              <div class="text-[10px] text-gray-400 mt-0.5">
                {{ row.video_width }}×{{ row.video_height }} · {{ (row.video_duration_seconds || 0).toFixed(1) }}s
              </div>
            </template>
          </el-table-column>
          <el-table-column label="ID" width="80">
            <template #default="{ row }">
              <span class="text-xs font-mono">#{{ row.id }}</span>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="素材库（视频）" name="material">
        <div class="flex items-center gap-2 mb-2">
          <el-button size="small" :loading="materialsLoading" @click="loadMaterials">刷新</el-button>
          <span class="text-xs text-gray-500">仅显示 video 类型素材，最多 200 条</span>
        </div>
        <el-table
          :data="videoMaterials"
          :height="280"
          highlight-current-row
          @current-change="onMaterialRowSelect"
          v-loading="materialsLoading"
        >
          <el-table-column label="文件" min-width="280">
            <template #default="{ row }">
              <div class="text-xs font-mono break-all">{{ row.file_name }}</div>
              <div class="text-[10px] text-gray-400 mt-0.5">
                {{ formatSize(row.file_size) }} · {{ row.library_kind }}
                <span v-if="row.product_name"> · {{ row.product_name }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="ID" width="80">
            <template #default="{ row }">
              <span class="text-xs font-mono">#{{ row.id }}</span>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import * as sourceVideoApi from "../../api/sourceVideo";
import * as materialApi from "../../api/material";

const emit = defineEmits(["update:selection"]);

const activeTab = ref("upload");
const uploadFile = ref(null);
const sourceVideos = ref([]);
const sourcesLoading = ref(false);
const videoMaterials = ref([]);
const materialsLoading = ref(false);

onMounted(() => {
  loadSources();
  loadMaterials();
});

async function loadSources() {
  sourcesLoading.value = true;
  try {
    const data = await sourceVideoApi.listSourceVideos();
    sourceVideos.value = Array.isArray(data?.items)
      ? data.items
      : Array.isArray(data)
        ? data
        : [];
  } catch (e) {
    ElMessage.error(`加载原视频失败：${e?.message || e}`);
  } finally {
    sourcesLoading.value = false;
  }
}

async function loadMaterials() {
  materialsLoading.value = true;
  try {
    const data = await materialApi.listMaterials({ file_type: "video", limit: 200 });
    videoMaterials.value = Array.isArray(data?.items)
      ? data.items
      : Array.isArray(data)
        ? data
        : [];
  } catch (e) {
    ElMessage.error(`加载素材库失败：${e?.message || e}`);
  } finally {
    materialsLoading.value = false;
  }
}

function onFileChange(file) {
  uploadFile.value = file.raw || null;
  emit("update:selection", { type: "upload", file: uploadFile.value, ref: null });
}

function clearUpload() {
  uploadFile.value = null;
  emit("update:selection", null);
}

function onSourceRowSelect(row) {
  if (!row) return;
  uploadFile.value = null;
  emit("update:selection", { type: "source", file: null, ref: String(row.id) });
}

function onMaterialRowSelect(row) {
  if (!row) return;
  uploadFile.value = null;
  emit("update:selection", { type: "material", file: null, ref: String(row.id) });
}

function onTabChange() {
  uploadFile.value = null;
  emit("update:selection", null);
}

function formatSize(bytes) {
  if (!bytes) return "0 B";
  const mb = bytes / (1024 * 1024);
  if (mb >= 1024) return `${(mb / 1024).toFixed(2)} GB`;
  if (mb >= 1) return `${mb.toFixed(1)} MB`;
  return `${(bytes / 1024).toFixed(0)} KB`;
}
</script>
