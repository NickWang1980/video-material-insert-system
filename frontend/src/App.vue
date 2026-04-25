<template>
  <div class="min-h-screen bg-white dark:bg-gray-900 text-black dark:text-gray-100">
    <div class="flex">
      <Sidebar :collapsed="sidebarCollapsed" @toggle="toggleSidebar" />
      <div class="flex-1 min-w-0 transition-all duration-200">
        <Header :is-dark="isDark" @toggle-dark="toggleDark" />
        <main class="p-8">
          <RouterView />
        </main>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import Sidebar from "./components/layout/Sidebar.vue";
import Header from "./components/layout/Header.vue";

const SIDEBAR_KEY = "vmis_sidebar_collapsed";
const DARK_KEY = "vmis_dark_mode";

const sidebarCollapsed = ref(localStorage.getItem(SIDEBAR_KEY) === "1");
const isDark = ref(localStorage.getItem(DARK_KEY) === "1");

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value;
  localStorage.setItem(SIDEBAR_KEY, sidebarCollapsed.value ? "1" : "0");
}

function toggleDark() {
  isDark.value = !isDark.value;
  localStorage.setItem(DARK_KEY, isDark.value ? "1" : "0");
  if (isDark.value) {
    document.documentElement.classList.add("dark");
  } else {
    document.documentElement.classList.remove("dark");
  }
}

onMounted(() => {
  if (isDark.value) {
    document.documentElement.classList.add("dark");
  }
});
</script>
