<template>
  <aside
    class="h-screen sticky top-0 border-r border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 transition-all duration-200"
    :class="collapsed ? 'w-[72px]' : 'w-[240px]'"
  >
    <div class="p-4 border-b border-gray-100 dark:border-gray-700">
      <div class="flex items-center" :class="collapsed ? 'justify-center' : 'justify-between gap-3'">
        <div class="flex items-center gap-3 min-w-0">
          <img src="/bzy_logo.png" alt="八爪鱼Logo" class="w-8 h-8 rounded-lg object-cover flex-none" />
          <div v-if="!collapsed" class="text-base font-bold leading-tight truncate text-gray-900 dark:text-gray-100">自动化剪辑工具</div>
        </div>
        <el-button text class="!px-2 dark:!text-gray-300" @click="$emit('toggle')">
          {{ collapsed ? "»" : "«" }}
        </el-button>
      </div>
      <div v-if="!collapsed" class="text-xs text-gray-500 dark:text-gray-400 mt-2">V2.0</div>
    </div>

    <nav class="p-3 space-y-1">
      <!-- Collapsed mode: flatten children, show short codes -->
      <template v-if="collapsed">
        <RouterLink
          v-for="leaf in flatLeaves"
          :key="leaf.to"
          :to="leaf.to"
          class="block rounded-xl transition-colors px-0 py-2 text-center"
          :class="$route.path === leaf.to
            ? 'bg-black text-white dark:bg-white dark:text-gray-900'
            : 'text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'"
          :title="leaf.label"
        >
          <span>{{ leaf.short }}</span>
        </RouterLink>
      </template>

      <!-- Expanded mode: tree with collapsible groups -->
      <template v-else>
        <template v-for="item in items" :key="item.key || item.to">
          <!-- Leaf at top level -->
          <RouterLink
            v-if="!item.children"
            :to="item.to"
            class="block rounded-xl transition-colors px-4 py-2"
            :class="$route.path === item.to
              ? 'bg-black text-white dark:bg-white dark:text-gray-900'
              : 'text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'"
          >
            {{ item.label }}
          </RouterLink>

          <!-- Group with children -->
          <div v-else class="select-none">
            <button
              type="button"
              class="w-full flex items-center justify-between rounded-xl px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              @click="toggleGroup(item.key)"
            >
              <span>{{ item.label }}</span>
              <span class="text-xs text-gray-400 transition-transform duration-150"
                    :class="groupExpanded[item.key] ? 'rotate-90' : ''">▶</span>
            </button>
            <div v-show="groupExpanded[item.key]" class="mt-1 pl-3 space-y-1">
              <RouterLink
                v-for="child in item.children"
                :key="child.to"
                :to="child.to"
                class="block rounded-xl transition-colors px-4 py-2 text-sm"
                :class="$route.path === child.to
                  ? 'bg-black text-white dark:bg-white dark:text-gray-900'
                  : 'text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700'"
              >
                {{ child.label }}
              </RouterLink>
            </div>
          </div>
        </template>
      </template>
    </nav>
  </aside>
</template>

<script setup>
import { computed, reactive, watch } from "vue";
import { useRoute } from "vue-router";
import { useAuthStore } from "../../store/modules/auth";

defineProps({
  collapsed: {
    type: Boolean,
    default: false,
  },
});

defineEmits(["toggle"]);

const authStore = useAuthStore();
const route = useRoute();

const GROUP_STATE_KEY = "vmis_sidebar_groups";

const allItems = [
  { to: "/",               label: "控制台",   short: "控", moduleKey: "console" },
  { to: "/rough-cut/unit", label: "混剪单元", short: "混", moduleKey: "rough_cut" },
  {
    key: "material_insert", label: "素材插入",
    children: [
      { to: "/materials",     label: "素材库",   short: "材", moduleKey: "materials" },
      { to: "/source-videos", label: "原视频",   short: "源", moduleKey: "source_videos" },
      { to: "/configs",       label: "配置模板", short: "模", moduleKey: "configs" },
      { to: "/tasks",         label: "任务管理", short: "任", moduleKey: "tasks" },
    ],
  },
  {
    key: "settings_group", label: "设置",
    children: [
      { to: "/audit",       label: "操作历史", short: "历", moduleKey: "audit" },
      { to: "/admin/users", label: "权限控制", short: "权", moduleKey: "user_management", adminOnly: true },
      { to: "/settings",    label: "系统设置", short: "设", moduleKey: "settings" },
    ],
  },
];

function _allowedLeaf(leaf) {
  if (leaf.adminOnly && !authStore.isAdmin) return false;
  if (authStore.isAdmin) return true;
  return authStore.allowedModules.includes(leaf.moduleKey);
}

const items = computed(() =>
  allItems
    .map((item) => {
      if (item.children) {
        const visible = item.children.filter(_allowedLeaf);
        return visible.length ? { ...item, children: visible } : null;
      }
      return _allowedLeaf(item) ? item : null;
    })
    .filter(Boolean)
);

const flatLeaves = computed(() => {
  const out = [];
  for (const item of items.value) {
    if (item.children) out.push(...item.children);
    else out.push(item);
  }
  return out;
});

function _loadGroupState() {
  try {
    const saved = JSON.parse(localStorage.getItem(GROUP_STATE_KEY) || "{}");
    return { material_insert: true, settings_group: true, ...saved };
  } catch {
    return { material_insert: true, settings_group: true };
  }
}

const groupExpanded = reactive(_loadGroupState());

function toggleGroup(key) {
  groupExpanded[key] = !groupExpanded[key];
  localStorage.setItem(GROUP_STATE_KEY, JSON.stringify(groupExpanded));
}

watch(
  () => route.path,
  (path) => {
    for (const item of allItems) {
      if (item.children?.some((c) => c.to === path)) {
        groupExpanded[item.key] = true;
      }
    }
  },
  { immediate: true }
);
</script>
