<template>
  <Transition name="shell-fade" mode="out-in">
    <!-- Login page: no chrome -->
    <div v-if="isLoginPage" key="login" class="min-h-screen">
      <RouterView />
    </div>

    <!-- App shell -->
    <div v-else key="shell" :class="appShellClass">
      <div class="flex">
        <Sidebar :collapsed="sidebarCollapsed" @toggle="toggleSidebar" />
        <div class="flex-1 min-w-0 transition-all duration-200">
          <Header :theme="theme" @set-theme="setTheme" />
          <main class="p-8">
            <RouterView v-slot="{ Component, route }">
              <Transition name="page-fade" mode="out-in">
                <component :is="Component" :key="route.path" />
              </Transition>
            </RouterView>
          </main>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { useRoute } from "vue-router";
import Sidebar from "./components/layout/Sidebar.vue";
import Header from "./components/layout/Header.vue";

const SIDEBAR_KEY = "vmis_sidebar_collapsed";
const THEME_KEY   = "vmis_theme";

const route = useRoute();
const isLoginPage = computed(() => route.name === "login");
const sidebarCollapsed = ref(localStorage.getItem(SIDEBAR_KEY) === "1");

function _resolveInitialTheme() {
  const saved = localStorage.getItem(THEME_KEY);
  if (saved) return saved;
  // backward-compat: migrate old vmis_dark_mode boolean
  return localStorage.getItem("vmis_dark_mode") === "1" ? "dark" : "light";
}

const theme = ref(_resolveInitialTheme());

const appShellClass = computed(() =>
  theme.value === "glass"
    ? "min-h-screen glass-app-shell"
    : "min-h-screen bg-white dark:bg-gray-900 text-black dark:text-gray-100"
);

function _applyTheme(t) {
  document.documentElement.classList.remove("dark", "glass");
  if (t === "dark")  document.documentElement.classList.add("dark");
  if (t === "glass") document.documentElement.classList.add("glass");
}

function setTheme(t) {
  theme.value = t;
  localStorage.setItem(THEME_KEY, t);
  _applyTheme(t);
}

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value;
  localStorage.setItem(SIDEBAR_KEY, sidebarCollapsed.value ? "1" : "0");
}

onMounted(() => _applyTheme(theme.value));
</script>

<style scoped>
/* ── Page-level route transitions (nav-tree switching) ── */
.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}
.page-fade-enter-from {
  opacity: 0;
  transform: translateY(6px);
}
.page-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

/* ── Shell-level transition (login → app or app → login) ── */
.shell-fade-enter-active,
.shell-fade-leave-active {
  transition: opacity 0.28s ease;
}
.shell-fade-enter-from,
.shell-fade-leave-to {
  opacity: 0;
}
</style>
