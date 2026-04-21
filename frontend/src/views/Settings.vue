<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <el-button @click="load">刷新</el-button>
        <el-button type="primary" @click="save">保存</el-button>
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
            <div class="text-sm font-medium mb-2">ASR模型</div>
            <el-select v-model="form.asr_model" class="w-full">
              <el-option label="small（默认）" value="small" />
              <el-option label="medium" value="medium" />
            </el-select>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import * as settingsApi from "../api/settings";

const loading = ref(false);
const form = reactive({
  output_format: "MP4",
  resolution: "1080P",
  video_bitrate_kbps: 6000,
  subtitle_encoding: "utf-8",
  subtitle_time_offset_seconds: 0,
  asr_model: "small",
});

onMounted(load);

async function load() {
  loading.value = true;
  try {
    const data = await settingsApi.getSettings();
    Object.assign(form, data);
  } finally {
    loading.value = false;
  }
}

async function save() {
  await settingsApi.updateSettings({ ...form });
  ElMessage.success("已保存");
}
</script>
