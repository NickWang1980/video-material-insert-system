<template>
  <div class="min-h-screen bg-white text-black">
    <div class="flex">
      <Sidebar :collapsed="sidebarCollapsed" @toggle="toggleSidebar" />
      <div class="flex-1 min-w-0 transition-all duration-200">
        <Header />
        <main class="p-8">
          <RouterView />
        </main>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";
import Sidebar from "./components/layout/Sidebar.vue";
import Header from "./components/layout/Header.vue";

const STORAGE_KEY = "vmis_sidebar_collapsed";
const sidebarCollapsed = ref(localStorage.getItem(STORAGE_KEY) === "1");

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value;
  localStorage.setItem(STORAGE_KEY, sidebarCollapsed.value ? "1" : "0");
}
</script>
