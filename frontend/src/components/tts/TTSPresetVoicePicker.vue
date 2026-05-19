<template>
  <div class="tts-preset-voice-picker space-y-3">
    <div
      v-if="props.modelValue"
      class="text-sm text-gray-600"
    >
      {{ t("tts.preset.selected", { name: props.modelValue }) }}
    </div>

    <div
      v-if="!voiceList.length"
      class="text-sm text-gray-400 py-6 text-center border border-dashed rounded"
    >
      {{ t("tts.preset.noVoices") }}
    </div>

    <div
      v-else
      class="grid grid-cols-3 gap-3"
    >
      <div
        v-for="voice in voiceList"
        :key="voice.code"
        class="cursor-pointer border rounded-md px-3 py-2 transition-colors hover:border-blue-400"
        :class="
          isSelected(voice)
            ? 'border-blue-500 bg-blue-50 ring-1 ring-blue-300'
            : 'border-gray-200 bg-white'
        "
        @click="onSelect(voice)"
      >
        <div class="text-base font-medium text-gray-800 truncate">
          {{ voice.code }}
        </div>
        <div
          v-if="voice.description"
          class="text-xs text-gray-500 mt-1 line-clamp-2"
        >
          {{ voice.description }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useI18n } from "vue-i18n";

const props = defineProps({
  modelValue: { type: String, default: "" },
  voices: { type: Array, default: () => [] },
});
const emit = defineEmits(["update:modelValue"]);

const { t } = useI18n();

const voiceList = computed(() =>
  Array.isArray(props.voices) ? props.voices : []
);

function isSelected(voice) {
  return voice && voice.code === props.modelValue;
}

function onSelect(voice) {
  if (!voice || !voice.code) return;
  emit("update:modelValue", voice.code);
}
</script>
