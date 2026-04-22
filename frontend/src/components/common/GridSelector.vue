<template>
  <div class="space-y-2">
    <div class="grid grid-cols-5 gap-2 w-[260px]">
      <button
        v-for="cell in cells"
        :key="cell.id"
        type="button"
        :disabled="!cell.position"
        class="h-11 rounded-lg border text-base leading-none transition"
        :class="cellClass(cell)"
        @click="select(cell)"
      >
        <span>{{ cell.label }}</span>
      </button>
    </div>
    <div class="text-xs text-gray-500">使用 5×5 参考网格中的红色 3×3 区域（映射九宫格 1-9）。</div>
  </div>
</template>

<script setup>
const props = defineProps({
  modelValue: { type: Number, required: true },
});
const emit = defineEmits(["update:modelValue"]);

const cells = [
  { id: 1, label: "1" },
  { id: 2, label: "2" },
  { id: 3, label: "3" },
  { id: 4, label: "4" },
  { id: 5, label: "5" },
  { id: 6, label: "6" },
  { id: 7, label: "7", position: 1 },
  { id: 8, label: "8", position: 2 },
  { id: 9, label: "9", position: 3 },
  { id: 10, label: "a" },
  { id: 11, label: "B" },
  { id: 12, label: "c", position: 4 },
  { id: 13, label: "d", position: 5 },
  { id: 14, label: "e", position: 6 },
  { id: 15, label: "f" },
  { id: 16, label: "G" },
  { id: 17, label: "h", position: 7 },
  { id: 18, label: "i", position: 8 },
  { id: 19, label: "j", position: 9 },
  { id: 20, label: "k" },
  { id: 21, label: "L" },
  { id: 22, label: "m" },
  { id: 23, label: "n" },
  { id: 24, label: "o" },
  { id: 25, label: "p" },
];

function cellClass(cell) {
  if (!cell.position) {
    return "border-transparent bg-[#d8efe7] text-[#22342f] cursor-not-allowed";
  }
  if (props.modelValue === cell.position) {
    return "border-black bg-black text-white";
  }
  return "border-[#d8efe7] bg-[#d8efe7] text-[#e74b4b] hover:border-black";
}

function select(cell) {
  if (!cell.position) return;
  emit("update:modelValue", cell.position);
}
</script>
