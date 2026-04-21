<template>
  <div class="grid grid-cols-3 gap-2 w-[180px]">
    <button
      v-for="n in 9"
      :key="n"
      class="h-12 rounded-xl border border-gray-200 hover:border-black"
      :class="modelValue === n ? 'bg-black text-white' : 'bg-white text-black'"
      type="button"
      @click="$emit('update:modelValue', n)"
    >
      {{ n }}
    </button>
  </div>
</template>

<script setup>
defineProps({
  modelValue: { type: Number, required: true },
});
defineEmits(["update:modelValue"]);
</script>
