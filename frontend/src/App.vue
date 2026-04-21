<template>
  <div class="min-h-screen bg-white text-black">
    <div class="flex">
      <Sidebar />
      <div class="flex-1 min-w-0">
        <Header />
        <main class="p-8">
          <RouterView />
        </main>
      </div>
    </div>
  </div>
</template>

<script setup>
import Sidebar from "./components/layout/Sidebar.vue";
import Header from "./components/layout/Header.vue";
</script>
