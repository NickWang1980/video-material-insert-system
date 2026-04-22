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
        <el-table-column label="关键词" width="160">
          <template #default="{ row }">
            <el-input v-model="row['关键词']" />
          </template>
        </el-table-column>

        <el-table-column label="素材目录" width="360">
          <template #default="{ row, $index }">
            <div class="space-y-2">
              <el-select
                v-model="row['素材库分类']"
                style="width: 120px"
                @change="onScopeChange(row, $index)"
              >
                <el-option label="定量素材" value="定量素材" />
                <el-option label="未归档" value="未归档" />
                <el-option label="产品分类素材" value="产品分类素材" />
              </el-select>
              <div class="flex gap-2" v-if="row['素材库分类'] === '产品分类素材'">
                <el-select
                  v-model="row['产品目录']"
                  style="width: 110px"
                  filterable
                  placeholder="产品目录"
                  @change="onProductChange(row, $index)"
                >
                  <el-option
                    v-for="item in productOptions"
                    :key="item.id"
                    :label="item.name"
                    :value="item.name"
                  />
                </el-select>
                <el-select
                  v-model="row['脚本子文件夹']"
                  style="width: 120px"
                  filterable
                  placeholder="脚本子文件夹"
                  @change="onScriptFolderChange(row, $index)"
                >
                  <el-option
                    v-for="item in scriptOptionsByProduct(row['产品目录'])"
                    :key="item.id"
                    :label="item.name"
                    :value="item.name"
                  />
                </el-select>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="素材类型 / 素材文件名" width="360">
          <template #default="{ row, $index }">
            <div class="space-y-2">
              <div class="flex items-center gap-2">
                <el-select
                  v-model="row['素材类型']"
                  style="width: 96px"
                  @change="onMaterialTypeChange(row, $index)"
                >
                  <el-option label="图片" value="图片" />
                  <el-option label="GIF" value="GIF" />
                  <el-option label="短视频" value="短视频" />
                </el-select>

                <el-select
                  v-model="row['素材文件名']"
                  style="width: 220px"
                  filterable
                  :disabled="materialOptionsByRow(row).length === 0"
                  :placeholder="materialOptionsByRow(row).length ? '请选择素材文件名' : '当前目录下暂无该类型素材'"
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

        <el-table-column label="提示音" width="300">
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
            <el-input-number
              v-model="row['显示时长(秒)']"
              :min="0"
              :step="0.1"
              :placeholder="row['素材类型'] === '短视频' ? '默认字幕时长' : '默认2秒'"
            />
          </template>
        </el-table-column>

        <el-table-column label="视频起始秒(秒)" width="140">
          <template #default="{ row }">
            <el-input-number
              v-model="row['视频起始秒(秒)']"
              :min="0"
              :step="0.1"
              :disabled="row['素材类型'] !== '短视频'"
            />
          </template>
        </el-table-column>

        <el-table-column label="视频持续秒(秒)" width="140">
          <template #default="{ row }">
            <el-input-number
              v-model="row['视频持续秒(秒)']"
              :min="0.1"
              :step="0.1"
              :disabled="row['素材类型'] !== '短视频'"
            />
          </template>
        </el-table-column>

        <el-table-column label="入场偏移(秒)" width="130">
          <template #default="{ row }">
            <el-input-number v-model="row['入场偏移(秒)']" :step="0.1" />
          </template>
        </el-table-column>

        <el-table-column label="九宫格位置" width="140">
          <template #default="{ row, $index }">
            <el-button size="small" @click="openPositionSelector($index)">
              位置 {{ normalizePosition(row['九宫格位置']) }}
            </el-button>
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

        <el-table-column label="素材大小" width="160">
          <template #default="{ row }">
            <el-select
              v-if="row['素材类型'] === '短视频'"
              v-model="row['素材宽度占比(%)']"
              style="width: 120px"
            >
              <el-option label="满屏 100%" :value="100" />
              <el-option label="大屏 70%" :value="70" />
            </el-select>
            <el-input-number
              v-else
              v-model="row['素材宽度占比(%)']"
              :min="5"
              :max="100"
              :step="1"
            />
          </template>
        </el-table-column>

        <el-table-column label="操作" width="80">
          <template #default="{ $index }">
            <el-button type="danger" size="small" @click="rows.splice($index, 1)">删</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>

  <el-dialog
    v-model="positionDialogVisible"
    title="选择九宫格位置（5×5参考）"
    width="360px"
    destroy-on-close
  >
    <GridSelector v-model="currentRowPosition" />
  </el-dialog>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";

import GridSelector from "../components/common/GridSelector.vue";
import { useConfigStore } from "../store/modules/config";
import { getMaterialTree, listMaterials, previewUrl } from "../api/material";

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
const materialTree = ref({ products: [] });
const hoverPreviewByRow = ref({});
const positionDialogVisible = ref(false);
const selectedPositionRowIndex = ref(-1);
let previewPlayer = null;

const productOptions = computed(() => materialTree.value.products || []);

const currentRowPosition = computed({
  get() {
    if (selectedPositionRowIndex.value < 0) return 1;
    const row = rows.value[selectedPositionRowIndex.value];
    if (!row) return 1;
    return normalizePosition(row["九宫格位置"]);
  },
  set(value) {
    if (selectedPositionRowIndex.value < 0) return;
    const row = rows.value[selectedPositionRowIndex.value];
    if (!row) return;
    row["九宫格位置"] = normalizePosition(value);
  },
});

function normalizePosition(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return 1;
  return Math.min(9, Math.max(1, Math.round(num)));
}

function normalizeSizeRatio(materialType, value) {
  if (materialType === "短视频") {
    return Number(value) === 100 ? 100 : 70;
  }
  const number = Number(value);
  if (!Number.isFinite(number)) return 25;
  return Math.min(100, Math.max(5, Math.round(number)));
}

function defaultDurationByType(materialType) {
  return materialType === "短视频" ? null : 2;
}

function defaultPositionByType(materialType) {
  return materialType === "短视频" ? 9 : 1;
}

function sortByFileName(items) {
  return [...items].sort((a, b) => a.file_name.localeCompare(b.file_name, "zh-Hans-CN"));
}

function materialTypeToFileType(materialType) {
  return MATERIAL_TYPE_MAP[materialType] || "image";
}

function scriptOptionsByProduct(productName) {
  const product = productOptions.value.find((item) => item.name === productName);
  return product?.scripts || [];
}

function materialOptionsByRow(row) {
  const fileType = materialTypeToFileType(row["素材类型"]);
  const all = materialPools.value[fileType] || [];
  const scope = row["素材库分类"] || "定量素材";

  if (scope === "产品分类素材") {
    const productName = (row["产品目录"] || "").trim();
    const scriptFolder = (row["脚本子文件夹"] || "").trim();
    if (!productName || !scriptFolder) return [];
    return all.filter((item) =>
      (item.folder_links || []).some(
        (link) =>
          link.product_name === productName &&
          link.script_folder_name === scriptFolder
      )
    );
  }

  if (scope === "未归档") {
    return all.filter((item) => item.library_kind === "unfiled");
  }

  return all.filter((item) => item.library_kind === "general");
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
  if (row["显示时长(秒)"] == null || row["显示时长(秒)"] === "") {
    row["显示时长(秒)"] = defaultDurationByType(row["素材类型"]);
  }
  if (!Number.isFinite(Number(row["九宫格位置"]))) {
    row["九宫格位置"] = defaultPositionByType(row["素材类型"]);
  }
  row["素材宽度占比(%)"] = normalizeSizeRatio(row["素材类型"], row["素材宽度占比(%)"]);
  clearHoveredMaterial(index);
}

function onScopeChange(row, index) {
  if (row["素材库分类"] !== "产品分类素材") {
    row["产品目录"] = "";
    row["脚本子文件夹"] = "";
  }
  row["素材文件名"] = "";
  clearHoveredMaterial(index);
}

function onProductChange(row, index) {
  row["脚本子文件夹"] = "";
  row["素材文件名"] = "";
  clearHoveredMaterial(index);
}

function onScriptFolderChange(row, index) {
  row["素材文件名"] = "";
  clearHoveredMaterial(index);
}

function isImageLike(material) {
  if (!material) return false;
  return material.file_type === "image" || material.file_type === "gif";
}

function openPositionSelector(index) {
  selectedPositionRowIndex.value = index;
  positionDialogVisible.value = true;
}

function addRow() {
  rows.value.push({
    关键词: "",
    素材库分类: "定量素材",
    产品目录: "",
    脚本子文件夹: "",
    素材文件名: "",
    素材类型: "图片",
    提示音: "随机",
    "显示时长(秒)": 2,
    "入场偏移(秒)": 0,
    九宫格位置: 1,
    透明度: 100,
    是否循环: 0,
    触发规则: "每次触发",
    "素材宽度占比(%)": 25,
    "视频起始秒(秒)": 0,
    "视频持续秒(秒)": null,
  });
}

function normalizeRow(row) {
  const materialType = row["素材类型"] ?? "图片";
  const durationRaw = row["显示时长(秒)"];
  const scope = row["素材库分类"] || "定量素材";
  return {
    关键词: row["关键词"] ?? "",
    素材库分类: scope,
    产品目录: scope === "产品分类素材" ? row["产品目录"] ?? "" : "",
    脚本子文件夹: scope === "产品分类素材" ? row["脚本子文件夹"] ?? "" : "",
    素材文件名: row["素材文件名"] ?? "",
    素材类型: materialType,
    提示音: row["提示音"] ?? "随机",
    "显示时长(秒)": durationRaw == null || durationRaw === "" ? defaultDurationByType(materialType) : durationRaw,
    "入场偏移(秒)": row["入场偏移(秒)"] ?? 0,
    九宫格位置: normalizePosition(row["九宫格位置"] ?? defaultPositionByType(materialType)),
    透明度: row["透明度"] ?? 100,
    是否循环: row["是否循环"] ?? 0,
    触发规则: row["触发规则"] ?? "每次触发",
    "素材宽度占比(%)": normalizeSizeRatio(materialType, row["素材宽度占比(%)"] ?? (materialType === "短视频" ? 70 : 25)),
    "视频起始秒(秒)": row["视频起始秒(秒)"] ?? 0,
    "视频持续秒(秒)": row["视频持续秒(秒)"] ?? null,
  };
}

async function loadMaterialPools() {
  const [images, gifs, videos, audios, tree] = await Promise.all([
    listMaterials({ file_type: "image" }),
    listMaterials({ file_type: "gif" }),
    listMaterials({ file_type: "video" }),
    listMaterials({ file_type: "audio" }),
    getMaterialTree(),
  ]);

  materialPools.value = {
    image: sortByFileName(images),
    gif: sortByFileName(gifs),
    video: sortByFileName(videos),
  };
  audioMaterials.value = sortByFileName(audios);
  materialTree.value = tree;
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
  if (!templateName.value) {
    ElMessage.warning("请先填写模板名称");
    return;
  }
  const payload = {
    template_name: templateName.value,
    description: description.value || null,
    config_content: rows.value.map(normalizeRow),
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
