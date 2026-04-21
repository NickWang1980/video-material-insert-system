<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-bold">{{ isEdit ? "编辑模板" : "新建模板" }}</h1>
      <div class="flex items-center gap-2">
        <el-upload :auto-upload="false" :show-file-list="false" accept=".csv" :on-change="onImport">
          <el-button>导入CSV</el-button>
        </el-upload>
        <el-button @click="addRow">添加一行</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </div>
    </div>

    <div class="p-6 rounded-xl border border-gray-200 shadow-card space-y-4">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <div class="text-sm font-medium mb-2">模板名称</div>
          <el-input v-model="templateName" placeholder="请输入模板名称" />
        </div>
        <div>
          <div class="text-sm font-medium mb-2">描述</div>
          <el-input v-model="description" placeholder="可选" />
        </div>
      </div>

      <el-table :data="rows" stripe style="width: 100%">
        <el-table-column label="关键字" width="160">
          <template #default="{ row }">
            <el-input v-model="row['关键字']" />
          </template>
        </el-table-column>

        <el-table-column label="素材类型 / 素材文件名" width="520">
          <template #default="{ row, $index }">
            <div class="space-y-2">
              <div class="flex items-center gap-2">
                <el-select
                  v-model="row['素材类型']"
                  style="width: 110px"
                  @change="onMaterialTypeChange(row, $index)"
                >
                  <el-option label="图片" value="图片" />
                  <el-option label="GIF" value="GIF" />
                  <el-option label="短视频" value="短视频" />
                </el-select>

                <el-select
                  v-model="row['素材文件名']"
                  style="width: 300px"
                  filterable
                  :disabled="materialOptionsByRow(row).length === 0"
                  :placeholder="materialOptionsByRow(row).length ? '请选择素材文件名' : '该类型下暂无素材'"
                  @visible-change="(visible) => onMaterialSelectVisibleChange($index, visible)"
                >
                  <el-option
                    v-for="material in materialOptionsByRow(row)"
                    :key="material.id"
                    :label="material.file_name"
                    :value="material.file_name"
                  >
                    <div class="truncate" @mouseenter="setHoveredMaterial($index, material)">
                      {{ material.file_name }}
                    </div>
                  </el-option>
                </el-select>
              </div>

              <div v-if="previewMaterialForRow(row, $index)" class="rounded-lg border border-gray-200 bg-gray-50 p-2">
                <div class="text-xs text-gray-600 truncate mb-1">
                  预览：{{ previewMaterialForRow(row, $index).file_name }}
                </div>
                <img
                  v-if="isImageLike(previewMaterialForRow(row, $index))"
                  :src="previewUrl(previewMaterialForRow(row, $index).id)"
                  class="w-24 h-24 rounded object-cover border border-gray-200"
                  alt="material-preview"
                />
                <video
                  v-else
                  :src="previewUrl(previewMaterialForRow(row, $index).id)"
                  class="w-24 h-24 rounded object-cover border border-gray-200"
                  muted
                  loop
                  autoplay
                  playsinline
                ></video>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="提示音" width="320">
          <template #default="{ row }">
            <div class="flex items-center gap-2">
              <el-select v-model="row['提示音']" style="width: 190px">
                <el-option label="随机" value="随机" />
                <el-option
                  v-for="audio in audioMaterials"
                  :key="audio.id"
                  :label="audio.file_name"
                  :value="audio.file_name"
                />
              </el-select>
              <el-button size="small" @click="previewCueSound(row)" :disabled="!canPreviewCueSound(row)">
                试听
              </el-button>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="显示时长(秒)" width="130">
          <template #default="{ row }">
            <el-input-number v-model="row['显示时长(秒)']" :min="0" :step="0.1" />
          </template>
        </el-table-column>

        <el-table-column label="入场偏移(秒)" width="130">
          <template #default="{ row }">
            <el-input-number v-model="row['入场偏移(秒)']" :step="0.1" />
          </template>
        </el-table-column>

        <el-table-column label="九宫格位置" width="120">
          <template #default="{ row }">
            <el-input-number v-model="row['九宫格位置']" :min="1" :max="9" />
          </template>
        </el-table-column>

        <el-table-column label="透明度" width="110">
          <template #default="{ row }">
            <el-input-number v-model="row['透明度']" :min="0" :max="100" />
          </template>
        </el-table-column>

        <el-table-column label="循环" width="90">
          <template #default="{ row }">
            <el-switch v-model="row['是否循环']" :active-value="1" :inactive-value="0" />
          </template>
        </el-table-column>

        <el-table-column label="触发规则" width="120">
          <template #default="{ row }">
            <el-select v-model="row['触发规则']" style="width: 100%">
              <el-option label="首次触发" value="首次触发" />
              <el-option label="每次触发" value="每次触发" />
            </el-select>
          </template>
        </el-table-column>

        <el-table-column label="素材宽度占比(%)" width="150">
          <template #default="{ row }">
            <el-input-number v-model="row['素材宽度占比(%)']" :min="5" :max="80" :step="1" />
          </template>
        </el-table-column>

        <el-table-column label="操作" width="80">
          <template #default="{ $index }">
            <el-button type="danger" size="small" @click="rows.splice($index, 1)">删</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pt-4 border-t border-gray-100">
        <div class="font-bold mb-2">九宫格位置选择器</div>
        <div class="flex items-center gap-6">
          <GridSelector v-model="grid" />
          <div class="text-sm text-gray-500">
            选择后会写入当前“选中行”的九宫格位置（默认第一行）。
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";

import GridSelector from "../components/common/GridSelector.vue";
import { useConfigStore } from "../store/modules/config";
import { listMaterials, previewUrl } from "../api/material";

const props = defineProps({ id: { type: String, default: null } });
const isEdit = computed(() => !!props.id);
const templateId = computed(() => (props.id ? Number(props.id) : null));

const MATERIAL_TYPE_MAP = {
  图片: "image",
  GIF: "gif",
  短视频: "video",
};

const store = useConfigStore();
const router = useRouter();

const templateName = ref("");
const description = ref("");
const rows = ref([]);
const materialPools = ref({
  image: [],
  gif: [],
  video: [],
});
const audioMaterials = ref([]);
const hoverPreviewByRow = ref({});
let previewPlayer = null;

const grid = ref(9);
watch(grid, (value) => {
  if (!rows.value.length) return;
  rows.value[0]["九宫格位置"] = value;
});

function sortByFileName(items) {
  return [...items].sort((a, b) => a.file_name.localeCompare(b.file_name, "zh-Hans-CN"));
}

function materialTypeToFileType(materialType) {
  return MATERIAL_TYPE_MAP[materialType] || "image";
}

function materialOptionsByRow(row) {
  const fileType = materialTypeToFileType(row["素材类型"]);
  return materialPools.value[fileType] || [];
}

function findMaterialByName(row) {
  return materialOptionsByRow(row).find((item) => item.file_name === row["素材文件名"]) || null;
}

function setHoveredMaterial(index, material) {
  hoverPreviewByRow.value = {
    ...hoverPreviewByRow.value,
    [index]: material,
  };
}

function clearHoveredMaterial(index) {
  const next = { ...hoverPreviewByRow.value };
  delete next[index];
  hoverPreviewByRow.value = next;
}

function onMaterialSelectVisibleChange(index, visible) {
  if (!visible) {
    clearHoveredMaterial(index);
  }
}

function previewMaterialForRow(row, index) {
  return hoverPreviewByRow.value[index] || findMaterialByName(row);
}

function onMaterialTypeChange(row, index) {
  const options = materialOptionsByRow(row);
  const exists = options.some((item) => item.file_name === row["素材文件名"]);
  if (!exists) {
    row["素材文件名"] = "";
  }
  clearHoveredMaterial(index);
}

function isImageLike(material) {
  if (!material) return false;
  return material.file_type === "image" || material.file_type === "gif";
}

function addRow() {
  rows.value.push({
    关键字: "",
    素材文件名: "",
    素材类型: "图片",
    提示音: "随机",
    "显示时长(秒)": null,
    "入场偏移(秒)": 0,
    九宫格位置: 9,
    透明度: 100,
    是否循环: 0,
    触发规则: "每次触发",
    "素材宽度占比(%)": 25,
  });
}

function normalizeRow(row) {
  const normalized = {
    关键字: row["关键字"] ?? "",
    素材文件名: row["素材文件名"] ?? "",
    素材类型: row["素材类型"] ?? "图片",
    提示音: row["提示音"] ?? "随机",
    "显示时长(秒)": row["显示时长(秒)"] ?? null,
    "入场偏移(秒)": row["入场偏移(秒)"] ?? 0,
    九宫格位置: row["九宫格位置"] ?? 9,
    透明度: row["透明度"] ?? 100,
    是否循环: row["是否循环"] ?? 0,
    触发规则: row["触发规则"] ?? "每次触发",
    "素材宽度占比(%)": row["素材宽度占比(%)"] ?? 25,
  };
  return normalized;
}

async function loadMaterialPools() {
  const [images, gifs, videos, audios] = await Promise.all([
    listMaterials({ file_type: "image" }),
    listMaterials({ file_type: "gif" }),
    listMaterials({ file_type: "video" }),
    listMaterials({ file_type: "audio" }),
  ]);

  materialPools.value = {
    image: sortByFileName(images),
    gif: sortByFileName(gifs),
    video: sortByFileName(videos),
  };
  audioMaterials.value = sortByFileName(audios);
}

function stopPreview() {
  if (!previewPlayer) return;
  previewPlayer.pause();
  previewPlayer.currentTime = 0;
  previewPlayer = null;
}

function resolvePreviewAudio(row) {
  if (!audioMaterials.value.length) return null;
  const cue = (row["提示音"] || "随机").trim() || "随机";
  if (cue === "随机") {
    const pick = Math.floor(Math.random() * audioMaterials.value.length);
    return audioMaterials.value[pick];
  }
  return audioMaterials.value.find((item) => item.file_name === cue) || null;
}

function canPreviewCueSound(row) {
  if (!audioMaterials.value.length) return false;
  const cue = (row["提示音"] || "随机").trim() || "随机";
  if (cue === "随机") return true;
  return audioMaterials.value.some((item) => item.file_name === cue);
}

function previewCueSound(row) {
  const selected = resolvePreviewAudio(row);
  if (!selected) {
    ElMessage.warning("无可用音效素材可试听");
    return;
  }
  stopPreview();
  previewPlayer = new Audio(previewUrl(selected.id));
  previewPlayer.play().catch(() => {
    ElMessage.error("试听失败");
    stopPreview();
  });
}

onMounted(async () => {
  await loadMaterialPools();
  if (isEdit.value) {
    const template = await store.getTemplate(templateId.value);
    templateName.value = template.template_name;
    description.value = template.description || "";
    rows.value = (template.config_content || []).map(normalizeRow);
  } else {
    addRow();
  }
});

onBeforeUnmount(() => {
  stopPreview();
});

async function save() {
  if (!templateName.value) return;
  const payload = {
    template_name: templateName.value,
    description: description.value || null,
    config_content: rows.value,
  };
  if (isEdit.value) {
    await store.updateTemplate(templateId.value, payload);
  } else {
    await store.createTemplate(payload);
  }
  ElMessage.success("已保存");
  router.push("/configs");
}

async function onImport(file) {
  try {
    const template = await store.importCsv(file.raw);
    ElMessage.success("已导入为新模板");
    router.push(`/configs/${template.id}`);
  } catch (error) {
    ElMessage.error(error.message || "导入失败");
  }
}
</script>
