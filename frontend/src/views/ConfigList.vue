<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <RouterLink to="/configs/new"><el-button type="primary">新建模板</el-button></RouterLink>
        <el-upload :auto-upload="false" :show-file-list="false" accept=".csv" :on-change="onImport">
          <el-button>导入CSV</el-button>
        </el-upload>
      </div>
    </div>

    <el-table :data="store.templates" stripe style="width: 100%">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="template_name" label="模板名称" min-width="180" />
      <el-table-column prop="keyword_preview" label="关键字" min-width="280">
        <template #default="{ row }">
          <span class="text-sm text-gray-700">{{ row.keyword_preview || "-" }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="description" label="描述" min-width="180" />
      <el-table-column label="操作" width="260">
        <template #default="{ row }">
          <div class="flex items-center gap-2">
            <RouterLink :to="`/configs/${row.id}`"><el-button size="small">编辑</el-button></RouterLink>
            <a :href="store.exportCsvUrl(row.id)" target="_blank"><el-button size="small">导出CSV</el-button></a>
            <el-button size="small" type="danger" @click="remove(row.id)">删除</el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { onMounted } from "vue";
import { ElMessage } from "element-plus";
import { useConfigStore } from "../store/modules/config";

const store = useConfigStore();

onMounted(() => store.fetchTemplates());

async function remove(id) {
  await store.deleteTemplate(id);
  await store.fetchTemplates();
  ElMessage.success("已删除");
}

async function onImport(file) {
  try {
    await store.importCsv(file.raw);
    await store.fetchTemplates();
    ElMessage.success("已导入");
  } catch (error) {
    ElMessage.error(error.message || "导入失败");
  }
}
</script>
