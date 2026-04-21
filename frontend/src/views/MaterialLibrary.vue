<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <el-upload multiple :auto-upload="false" :show-file-list="false" :on-change="onSelect">
        <el-button type="primary">批量上传</el-button>
      </el-upload>
    </div>

    <div class="flex items-center gap-2">
      <el-select v-model="fileType" placeholder="类型筛选" style="width: 200px" @change="reload">
        <el-option label="全部" value="" />
        <el-option label="图片" value="image" />
        <el-option label="GIF" value="gif" />
        <el-option label="短视频" value="video" />
        <el-option label="音效" value="audio" />
      </el-select>
      <el-button @click="reload">刷新</el-button>
    </div>

    <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-6" v-loading="store.loading">
      <div v-for="m in store.items" :key="m.id" class="p-3 rounded-xl border border-gray-200 shadow-card">
        <div class="aspect-square bg-gray-50 rounded-xl overflow-hidden flex items-center justify-center">
          <img v-if="m.file_type === 'image' || m.file_type === 'gif'" :src="store.previewUrl(m.id)" class="w-full h-full object-cover" />
          <div v-else-if="m.file_type === 'video'" class="text-sm text-gray-500">视频预览</div>
          <div v-else class="text-sm text-gray-500">音效素材</div>
        </div>
        <div class="mt-2 text-sm font-medium truncate" :title="m.file_name">{{ m.file_name }}</div>
        <div class="mt-1 text-xs text-gray-500">{{ m.file_type }} | {{ formatBytes(m.file_size) }}</div>
        <div class="mt-2 flex items-center gap-2">
          <el-button size="small" @click="rename(m)">重命名</el-button>
          <el-button size="small" type="danger" @click="remove(m.id)">删除</el-button>
        </div>
      </div>
    </div>
    <el-empty v-if="!store.loading && store.items.length === 0" description="暂无素材（请确认后端已启动，并上传素材）" />
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { useMaterialStore } from "../store/modules/material";
import { formatBytes } from "../utils/format";

const store = useMaterialStore();
const fileType = ref("");
let uploadTimer = null;
const pendingFiles = ref([]);

onMounted(() => reload());

async function reload() {
  try {
    await store.fetchList(fileType.value);
  } catch (e) {
    ElMessage.error(e.message || "获取素材列表失败（请确认后端已启动）");
  }
}

function onSelect(file, fileList) {
  pendingFiles.value = fileList.map((x) => x.raw).filter(Boolean);
  if (uploadTimer) clearTimeout(uploadTimer);
  uploadTimer = setTimeout(doUpload, 300);
}

async function doUpload() {
  const raws = pendingFiles.value;
  if (!raws || raws.length === 0) return;
  try {
    const res = await store.upload(raws);
    const failed = res.failed?.length || 0;
    const ok = res.success?.length || 0;
    await reload();
    if (failed) ElMessage.warning(`上传完成：成功 ${ok}，失败 ${failed}`);
    else ElMessage.success(`上传完成：成功 ${ok}`);
  } catch (e) {
    ElMessage.error(e.message || "上传失败");
  }
}

async function rename(m) {
  const { value } = await ElMessageBox.prompt("请输入新文件名（含后缀）", "重命名", {
    inputValue: m.file_name,
  });
  await store.rename(m.id, value);
  await reload();
  ElMessage.success("已重命名");
}

async function remove(id) {
  await store.remove(id);
  await reload();
  ElMessage.success("已删除");
}
</script>
