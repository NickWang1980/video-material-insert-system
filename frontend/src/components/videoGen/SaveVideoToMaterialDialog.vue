<template>
  <el-dialog
    v-model="visible"
    title="保存到素材库"
    width="480px"
    :close-on-click-modal="false"
  >
    <div class="space-y-4">
      <div>
        <div class="text-sm font-medium mb-1">显示名称</div>
        <el-input v-model="form.display_name" :placeholder="`video_gen_${taskId || ''}.mp4`" />
      </div>
      <div>
        <div class="text-sm font-medium mb-1">归类</div>
        <el-select v-model="form.library_kind" class="w-full">
          <el-option label="未分类（默认）" value="unfiled" />
          <el-option label="通用素材库" value="general" />
          <el-option label="产品素材库" value="product" />
        </el-select>
      </div>
      <div class="text-xs text-gray-500">
        Phase-1：仅支持基础三选；如需绑定到具体产品/脚本文件夹，请先保存后到「素材库」页继续归类。
      </div>
    </div>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="onConfirm">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { reactive, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { saveVideoGenToMaterial } from "../../api/videoGen";

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  taskId: { type: [Number, String], default: null },
});
const emit = defineEmits(["update:modelValue", "saved"]);

const visible = ref(props.modelValue);
watch(() => props.modelValue, (v) => (visible.value = v));
watch(visible, (v) => emit("update:modelValue", v));

const form = reactive({
  display_name: "",
  library_kind: "unfiled",
});
const saving = ref(false);

async function onConfirm() {
  if (!props.taskId) return;
  saving.value = true;
  try {
    const r = await saveVideoGenToMaterial(props.taskId, {
      display_name: form.display_name || null,
      library_kind: form.library_kind,
    });
    ElMessage.success(`已保存为素材 #${r.material_id}`);
    visible.value = false;
    emit("saved", r);
  } catch (e) {
    ElMessage.error(`保存失败：${e?.response?.data?.detail || e?.message || e}`);
  } finally {
    saving.value = false;
  }
}
</script>
