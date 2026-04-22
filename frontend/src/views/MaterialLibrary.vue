<template>
  <div class="grid grid-cols-[300px_1fr] gap-6 min-h-[620px]">
    <div class="rounded-xl border border-gray-200 bg-white p-4 space-y-3">
      <div class="text-sm font-semibold">素材目录</div>
      <el-tree
        ref="treeRef"
        :data="treeData"
        node-key="key"
        :expand-on-click-node="false"
        :default-expanded-keys="defaultExpandedKeys"
        :highlight-current="true"
        @node-click="onNodeClick"
      >
        <template #default="{ data }">
          <div
            class="w-full min-h-[28px] flex items-center"
            @dragover.prevent
            @drop.prevent="onDropToNode(data)"
          >
            <span class="text-sm">{{ data.label }}</span>
          </div>
        </template>
      </el-tree>

      <div class="pt-3 border-t border-gray-100 space-y-2">
        <div class="text-xs text-gray-500">目录操作</div>
        <div class="flex flex-wrap gap-2">
          <el-button v-if="selectedNodeType === 'product_root'" size="small" @click="createProduct">新建产品</el-button>
          <el-button v-if="selectedNodeType === 'product'" size="small" @click="createScriptFolder">新建子文件夹</el-button>
          <el-button v-if="selectedNodeType === 'product'" size="small" @click="renameProduct">重命名产品</el-button>
          <el-button v-if="selectedNodeType === 'product'" size="small" type="danger" @click="removeProduct">删除产品</el-button>
          <el-button v-if="selectedNodeType === 'script'" size="small" @click="renameScriptFolder">重命名子文件夹</el-button>
          <el-button v-if="selectedNodeType === 'script'" size="small" type="danger" @click="removeScriptFolder">删除子文件夹</el-button>
        </div>
      </div>
    </div>

    <div class="space-y-4">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="text-sm text-gray-600">当前目录：{{ currentPathLabel }}</div>

        <div class="flex flex-wrap items-center gap-2">
          <el-upload
            multiple
            :auto-upload="false"
            :show-file-list="false"
            :on-change="onSelect"
            :disabled="!canUpload"
          >
            <el-button type="primary" :disabled="!canUpload">批量上传到当前目录</el-button>
          </el-upload>
          <el-select v-model="fileType" placeholder="类型筛选" style="width: 140px" @change="reload">
            <el-option label="全部" value="" />
            <el-option label="图片" value="image" />
            <el-option label="GIF" value="gif" />
            <el-option label="短视频" value="video" />
            <el-option label="音效" value="audio" />
          </el-select>
          <el-segmented v-model="viewMode" :options="viewModeOptions" />
          <el-button @click="reload">刷新</el-button>
        </div>
      </div>

      <el-alert
        type="info"
        :closable="false"
        title="支持拖拽素材到左侧目录树进行归档；同一素材可归档到多个子文件夹。"
      />

      <el-alert
        v-if="!canUpload"
        type="warning"
        :closable="false"
        title="请先选择“定量素材 / 未归档 / 脚本子文件夹”后再上传素材。"
      />

      <div
        v-if="viewMode === 'thumbnail'"
        class="grid grid-cols-3 md:grid-cols-6 lg:grid-cols-8 gap-4"
        v-loading="store.loading"
      >
        <div
          v-for="material in store.items"
          :key="material.id"
          class="group rounded-xl border border-gray-200 overflow-hidden bg-white"
          draggable="true"
          @dragstart="onDragStart(material)"
        >
          <div
            class="aspect-square bg-gray-100 flex items-center justify-center cursor-pointer"
            @click="openPreview(material)"
          >
            <img
              v-if="isImageLike(material)"
              :src="store.previewUrl(material.id)"
              class="w-full h-full object-cover"
            />
            <video
              v-else-if="material.file_type === 'video'"
              :src="store.previewUrl(material.id)"
              class="w-full h-full object-cover"
              muted
              preload="metadata"
            />
            <span v-else class="text-xs text-gray-500">音频</span>
          </div>
          <div class="px-2 py-2 text-xs truncate" :title="material.file_name">{{ material.file_name }}</div>
          <div class="px-2 pb-2 text-[11px] text-gray-500 truncate" :title="materialPathTag(material)">{{ materialPathTag(material) }}</div>
          <div class="px-2 pb-2 flex items-center justify-between gap-1">
            <el-button size="small" text @click="rename(material)">重命名</el-button>
            <el-button v-if="selectedNodeType === 'script'" size="small" text @click="unfileFromCurrent(material)">移出</el-button>
            <el-button size="small" text type="danger" @click="remove(material.id)">删除</el-button>
          </div>
        </div>
      </div>

      <el-table
        v-else
        :data="store.items"
        stripe
        border
        style="width: 100%"
        v-loading="store.loading"
      >
        <el-table-column label="预览" width="120">
          <template #default="{ row }">
            <div
              class="w-20 h-12 rounded overflow-hidden bg-gray-100 flex items-center justify-center cursor-pointer"
              @click="openPreview(row)"
              draggable="true"
              @dragstart="onDragStart(row)"
            >
              <img v-if="isImageLike(row)" :src="store.previewUrl(row.id)" class="w-full h-full object-cover" />
              <video
                v-else-if="row.file_type === 'video'"
                :src="store.previewUrl(row.id)"
                class="w-full h-full object-cover"
                muted
                preload="metadata"
              />
              <span v-else class="text-[11px] text-gray-500">音频</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="file_name" label="文件名" min-width="220" show-overflow-tooltip />
        <el-table-column label="归档目录" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">{{ materialPathTag(row) }}</template>
        </el-table-column>
        <el-table-column prop="file_type" label="类型" width="100" />
        <el-table-column label="大小" width="120">
          <template #default="{ row }">{{ formatBytes(row.file_size) }}</template>
        </el-table-column>
        <el-table-column label="音轨状态" width="120">
          <template #default="{ row }">
            <span v-if="row.file_type === 'video'">{{ row.audio_removed ? "已去音轨" : "保留音轨" }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <div class="flex items-center gap-2">
              <el-button size="small" @click="openPreview(row)">预览</el-button>
              <el-button size="small" @click="rename(row)">重命名</el-button>
              <el-button v-if="selectedNodeType === 'script'" size="small" @click="unfileFromCurrent(row)">移出</el-button>
              <el-button size="small" type="danger" @click="remove(row.id)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!store.loading && store.items.length === 0" description="当前目录暂无素材" />
    </div>

    <el-dialog
      v-model="previewVisible"
      :title="previewMaterial ? `预览：${previewMaterial.file_name}` : '预览'"
      width="720px"
      destroy-on-close
    >
      <div
        v-if="previewMaterial"
        class="bg-gray-50 rounded-lg p-4 flex items-center justify-center min-h-[320px]"
      >
        <img
          v-if="isImageLike(previewMaterial)"
          :src="store.previewUrl(previewMaterial.id)"
          class="max-h-[520px] max-w-full object-contain"
        />
        <video
          v-else-if="previewMaterial.file_type === 'video'"
          :src="store.previewUrl(previewMaterial.id)"
          class="max-h-[520px] max-w-full"
          controls
          preload="metadata"
        ></video>
        <audio v-else :src="store.previewUrl(previewMaterial.id)" controls class="w-full"></audio>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { useMaterialStore } from "../store/modules/material";
import { formatBytes } from "../utils/format";

const store = useMaterialStore();
const treeRef = ref(null);
const viewMode = ref("thumbnail");
const viewModeOptions = [
  { label: "预览", value: "thumbnail" },
  { label: "详细", value: "list" },
];
const fileType = ref("");

const selectedNode = ref({ key: "general", type: "general", label: "定量素材" });
const defaultExpandedKeys = ref(["general", "unfiled", "product_root"]);
const draggingMaterial = ref(null);

let uploadTimer = null;
const pendingFiles = ref([]);
const previewVisible = ref(false);
const previewMaterial = ref(null);

const treeData = computed(() => {
  const products = (store.tree?.products || []).map((product) => ({
    key: `product_${product.id}`,
    id: product.id,
    type: "product",
    label: product.name,
    children: (product.scripts || []).map((script) => ({
      key: `script_${script.id}`,
      id: script.id,
      productId: product.id,
      productName: product.name,
      type: "script",
      label: script.name,
    })),
  }));

  return [
    {
      key: "general",
      type: "general",
      label: store.tree?.general_label || "定量素材",
    },
    {
      key: "unfiled",
      type: "unfiled",
      label: store.tree?.unfiled_label || "未归档",
    },
    {
      key: "product_root",
      type: "product_root",
      label: store.tree?.product_label || "产品分类素材",
      children: products,
    },
  ];
});

const selectedNodeType = computed(() => selectedNode.value?.type || "general");
const canUpload = computed(() => {
  return ["general", "unfiled", "script"].includes(selectedNodeType.value);
});

const currentPathLabel = computed(() => {
  const node = selectedNode.value;
  if (!node) return "-";
  if (node.type === "general") return "定量素材";
  if (node.type === "unfiled") return "未归档";
  if (node.type === "product_root") return "产品分类素材";
  if (node.type === "product") return `产品分类素材 / ${node.label}`;
  if (node.type === "script") return `产品分类素材 / ${node.productName} / ${node.label}`;
  return node.label;
});

onMounted(async () => {
  await reloadTree();
  await nextTick();
  treeRef.value?.setCurrentKey("general");
  await reload();
});

function isImageLike(material) {
  return material.file_type === "image" || material.file_type === "gif";
}

function currentFilters() {
  const node = selectedNode.value;
  const base = { file_type: fileType.value };
  if (!node) return base;
  if (node.type === "general") return { ...base, library_kind: "general" };
  if (node.type === "unfiled") return { ...base, library_kind: "unfiled" };
  if (node.type === "script") {
    return {
      ...base,
      script_folder_id: node.id,
    };
  }
  if (node.type === "product") {
    return {
      ...base,
      product_id: node.id,
    };
  }
  return base;
}

async function reloadTree() {
  try {
    await store.fetchTree();
  } catch (error) {
    ElMessage.error(error.message || "读取素材目录失败");
  }
}

async function reload() {
  try {
    await store.fetchList(currentFilters());
  } catch (error) {
    ElMessage.error(error.message || "获取素材列表失败");
  }
}

function onNodeClick(node) {
  selectedNode.value = node;
  reload();
}

function onDragStart(material) {
  draggingMaterial.value = material;
}

async function onDropToNode(targetNode) {
  const material = draggingMaterial.value;
  draggingMaterial.value = null;
  if (!material) return;

  try {
    if (targetNode.type === "script") {
      await store.fileMaterial(material.id, {
        target_type: "script",
        script_folder_id: targetNode.id,
      });
      ElMessage.success(`已归档到 ${targetNode.productName} / ${targetNode.label}`);
    } else if (targetNode.type === "general") {
      await store.fileMaterial(material.id, { target_type: "general" });
      ElMessage.success("已归档到定量素材");
    } else if (targetNode.type === "unfiled") {
      await store.fileMaterial(material.id, { target_type: "unfiled" });
      ElMessage.success("已归档到未归档");
    } else {
      return;
    }
    await reloadTree();
    await reload();
  } catch (error) {
    ElMessage.error(error.message || "拖拽归档失败");
  }
}

function onSelect(_file, fileList) {
  pendingFiles.value = fileList.map((item) => item.raw).filter(Boolean);
  if (uploadTimer) clearTimeout(uploadTimer);
  uploadTimer = setTimeout(doUpload, 300);
}

async function doUpload() {
  const raws = pendingFiles.value;
  if (!raws?.length) return;
  if (!canUpload.value) {
    ElMessage.warning("请先进入可上传的目录（定量素材/未归档/脚本子文件夹）");
    return;
  }

  const node = selectedNode.value;
  let meta = { library_kind: "unfiled" };
  if (node.type === "general") {
    meta = { library_kind: "general" };
  } else if (node.type === "script") {
    meta = { library_kind: "product", script_folder_id: node.id };
  }

  try {
    const result = await store.upload(raws, meta);
    const failed = result.failed?.length || 0;
    const success = result.success?.length || 0;
    await reloadTree();
    await reload();
    if (failed) {
      const failedText = result.failed
        .slice(0, 3)
        .map((item) => `${item.file}: ${item.reason}`)
        .join("；");
      ElMessage.warning(`上传完成：成功 ${success}，失败 ${failed}${failedText ? `（${failedText}）` : ""}`);
    } else {
      ElMessage.success(`上传完成：成功 ${success}`);
    }
  } catch (error) {
    ElMessage.error(error.message || "上传失败");
  }
}

function openPreview(material) {
  previewMaterial.value = material;
  previewVisible.value = true;
}

async function rename(material) {
  const { value } = await ElMessageBox.prompt("请输入新文件名（含后缀）", "重命名", {
    inputValue: material.file_name,
  });
  await store.rename(material.id, value);
  await reload();
  ElMessage.success("已重命名");
}

async function remove(id) {
  await store.remove(id);
  await reload();
  ElMessage.success("已删除");
}

async function unfileFromCurrent(material) {
  if (selectedNodeType.value !== "script") return;
  await store.unfileMaterialFromScript(material.id, selectedNode.value.id);
  await reloadTree();
  await reload();
  ElMessage.success("已移出当前脚本子文件夹");
}

async function createProduct() {
  const { value } = await ElMessageBox.prompt("请输入产品目录名称", "新建产品目录");
  await store.createProduct(value);
  await reloadTree();
  ElMessage.success("产品目录已创建");
}

async function renameProduct() {
  const node = selectedNode.value;
  if (node.type !== "product") return;
  const { value } = await ElMessageBox.prompt("请输入产品目录新名称", "重命名产品目录", {
    inputValue: node.label,
  });
  await store.renameProduct(node.id, value);
  await reloadTree();
  ElMessage.success("产品目录已重命名");
}

async function removeProduct() {
  const node = selectedNode.value;
  if (node.type !== "product") return;
  await ElMessageBox.confirm("删除后不可恢复，请确认产品目录已清空。", "删除产品目录", {
    type: "warning",
  });
  await store.deleteProduct(node.id);
  selectedNode.value = { key: "product_root", type: "product_root", label: "产品分类素材" };
  await reloadTree();
  await reload();
  ElMessage.success("产品目录已删除");
}

async function createScriptFolder() {
  const node = selectedNode.value;
  if (node.type !== "product") return;
  const { value } = await ElMessageBox.prompt("请输入脚本子文件夹名称", "新建脚本子文件夹");
  await store.createScriptFolder(node.id, value);
  await reloadTree();
  ElMessage.success("脚本子文件夹已创建");
}

async function renameScriptFolder() {
  const node = selectedNode.value;
  if (node.type !== "script") return;
  const { value } = await ElMessageBox.prompt("请输入脚本子文件夹新名称", "重命名脚本子文件夹", {
    inputValue: node.label,
  });
  await store.renameScriptFolder(node.id, value);
  await reloadTree();
  ElMessage.success("脚本子文件夹已重命名");
}

async function removeScriptFolder() {
  const node = selectedNode.value;
  if (node.type !== "script") return;
  await ElMessageBox.confirm("删除后不可恢复，请确认子文件夹已清空。", "删除脚本子文件夹", {
    type: "warning",
  });
  await store.deleteScriptFolder(node.id);
  selectedNode.value = {
    key: `product_${node.productId}`,
    id: node.productId,
    type: "product",
    label: node.productName,
  };
  await reloadTree();
  await reload();
  ElMessage.success("脚本子文件夹已删除");
}

function materialPathTag(material) {
  const links = material.folder_links || [];
  const parts = links.map((item) => `${item.product_name}/${item.script_folder_name}`);
  if (material.library_kind === "general") parts.unshift("定量素材");
  if (material.library_kind === "unfiled") parts.unshift("未归档");
  if (parts.length === 0) return "未归档";
  if (parts.length <= 2) return parts.join("，");
  return `${parts.slice(0, 2).join("，")} 等${parts.length}处`;
}
</script>
