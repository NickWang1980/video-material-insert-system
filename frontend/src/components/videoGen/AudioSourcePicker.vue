<template>
  <div class="space-y-3">
    <el-tabs v-model="activeTab" @tab-change="onTabChange">
      <el-tab-pane label="上传 wav/mp3" name="upload">
        <el-upload
          drag
          :multiple="false"
          :auto-upload="false"
          :show-file-list="false"
          :on-change="onFileChange"
          accept=".wav,.mp3,.flac,.m4a,.ogg"
        >
          <div class="p-6 text-center">
            <div class="text-3xl mb-1">🎵</div>
            <div class="text-sm text-gray-700">拖入音频文件，或点击选择</div>
            <div class="text-xs text-gray-400 mt-1">支持 wav / mp3 / flac / m4a / ogg，&lt;100 MB；建议干净人声</div>
          </div>
        </el-upload>
        <div v-if="uploadFile" class="text-xs text-gray-600 mt-2 flex items-center gap-2">
          <span class="font-mono break-all">{{ uploadFile.name }}</span>
          <span>· {{ formatSize(uploadFile.size) }}</span>
          <el-button text type="danger" size="small" @click="clearUpload">移除</el-button>
        </div>
      </el-tab-pane>

      <el-tab-pane label="TTS 历史" name="tts">
        <div v-if="!ttsHistory.length" class="text-sm text-gray-500 p-4 text-center">
          TTS 历史为空。先去
          <router-link to="/tts" class="text-blue-600 underline">语音生成</router-link>
          合成一段。
        </div>
        <el-table
          v-else
          :data="ttsHistory"
          :height="280"
          highlight-current-row
          @current-change="onTtsRowSelect"
        >
          <el-table-column label="文案" min-width="240">
            <template #default="{ row }">
              <div class="text-xs truncate" :title="row.text">{{ row.text || "(空)" }}</div>
              <div class="text-[10px] text-gray-400 mt-0.5">
                {{ formatTime(row.ts) }} · {{ row.language || "auto" }}
                <span v-if="row.voice"> · {{ row.voice }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="时长" width="80" align="right">
            <template #default="{ row }">
              <span class="text-xs">{{ row.duration_sec ? row.duration_sec.toFixed(1) : "—" }}s</span>
            </template>
          </el-table-column>
          <el-table-column label="试听" width="160">
            <template #default="{ row }">
              <audio :src="audioUrl(row.audio_url)" controls preload="none" class="w-full" style="height: 28px" />
            </template>
          </el-table-column>
        </el-table>
        <div v-if="selectedTts" class="text-xs text-green-700 mt-2">
          已选：{{ selectedTts.text || "(空)" }} · {{ selectedTts.duration_sec?.toFixed(1) || "—" }}s
        </div>
      </el-tab-pane>

      <el-tab-pane label="素材库（音频）" name="material">
        <div class="flex items-center gap-2 mb-2">
          <el-button size="small" :loading="materialsLoading" @click="loadMaterials">刷新</el-button>
          <span class="text-xs text-gray-500">仅显示 audio 类型素材，最多 200 条</span>
        </div>
        <el-table
          :data="audioMaterials"
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
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { useTTSStore } from "../../store/modules/tts";
import * as materialApi from "../../api/material";
import { getTTSAudioUrl } from "../../api/tts";

const emit = defineEmits(["update:selection"]);

const activeTab = ref("upload");
const uploadFile = ref(null);
const selectedTts = ref(null);
const selectedMaterial = ref(null);

const ttsStore = useTTSStore();
const ttsHistory = computed(() => ttsStore.history || []);

const audioMaterials = ref([]);
const materialsLoading = ref(false);

onMounted(() => {
  loadMaterials();
});

async function loadMaterials() {
  materialsLoading.value = true;
  try {
    const data = await materialApi.listMaterials({ file_type: "audio", limit: 200 });
    audioMaterials.value = Array.isArray(data?.items)
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
  selectedTts.value = null;
  selectedMaterial.value = null;
  emit("update:selection", {
    type: "upload",
    file: uploadFile.value,
    ref: null,
  });
}

function clearUpload() {
  uploadFile.value = null;
  emit("update:selection", null);
}

function onTtsRowSelect(row) {
  if (!row) return;
  selectedTts.value = row;
  uploadFile.value = null;
  selectedMaterial.value = null;
  emit("update:selection", {
    type: "tts",
    file: null,
    // backend expects the audio file path / filename — pass audio_url (full path) directly
    ref: row.audio_url || "",
  });
}

function onMaterialRowSelect(row) {
  if (!row) return;
  selectedMaterial.value = row;
  uploadFile.value = null;
  selectedTts.value = null;
  emit("update:selection", {
    type: "material",
    file: null,
    ref: String(row.id),
  });
}

function onTabChange() {
  // clear selection on tab switch to avoid stale state
  uploadFile.value = null;
  selectedTts.value = null;
  selectedMaterial.value = null;
  emit("update:selection", null);
}

function audioUrl(u) {
  return getTTSAudioUrl(u);
}

function formatSize(bytes) {
  if (!bytes) return "0 B";
  const mb = bytes / (1024 * 1024);
  if (mb >= 1) return `${mb.toFixed(1)} MB`;
  const kb = bytes / 1024;
  return `${kb.toFixed(0)} KB`;
}

function formatTime(ts) {
  if (!ts) return "";
  return new Date(ts).toLocaleString();
}
</script>
