<template>
  <div class="login-root">
    <!-- Seamless crossfade loop: two video elements swap at end -->
    <video ref="vid1" class="login-video-bg" :class="{ 'vid-active': activeSlot === 0 }"
           muted playsinline preload="auto" loop @timeupdate="onTimeUpdate">
      <source src="/login-bg.mp4" type="video/mp4" />
    </video>
    <video ref="vid2" class="login-video-bg" :class="{ 'vid-active': activeSlot === 1 }"
           muted playsinline preload="auto" loop @timeupdate="onTimeUpdate">
      <source src="/login-bg.mp4" type="video/mp4" />
    </video>
    <!-- Subtle dark veil so white text stays readable -->
    <div class="login-overlay" />
    <!-- Cover bottom-right video watermark -->
    <div class="login-watermark-mask" />

    <!-- Liquid glass card -->
    <div class="login-card">
      <div class="flex flex-col items-center mb-8">
<h1 class="text-2xl font-bold tracking-tight text-white drop-shadow">八爪鱼 智能剪辑工具 v2.3</h1>
        <p class="text-sm mt-1 text-white/60">请登录以继续</p>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @submit.prevent="handleLogin"
      >
        <el-form-item label="用户名" prop="username" class="glass-form-item">
          <el-input
            v-model="form.username"
            placeholder="请输入用户名"
            size="large"
            autofocus
            class="glass-input"
          />
        </el-form-item>

        <el-form-item label="密码" prop="password" class="glass-form-item">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            size="large"
            show-password
            class="glass-input"
            @keyup.enter="handleLogin"
          />
        </el-form-item>

        <el-alert
          v-if="errorMsg"
          :title="errorMsg"
          type="error"
          class="mb-4 glass-alert"
          :closable="false"
          show-icon
        />

        <el-button
          type="primary"
          size="large"
          class="login-btn w-full mt-2"
          :loading="loading"
          @click="handleLogin"
        >
          登 录
        </el-button>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from "vue";
import { useRouter, useRoute } from "vue-router";
import { useAuthStore } from "../store/modules/auth";

const router = useRouter();
const route = useRoute();
const authStore = useAuthStore();

// ── Video crossfade loop ─────────────────────────────
const vid1 = ref(null);
const vid2 = ref(null);
const activeSlot = ref(0); // 0 = vid1 visible, 1 = vid2 visible
const CROSSFADE = 1.5;     // seconds before end to start next video
let swapping = false;

onMounted(async () => {
  // Pre-decode vid2's first frame: play then immediately pause so the browser
  // has a rendered frame ready. Without this, vid2 shows black on first fade-in.
  const v2 = vid2.value;
  if (v2) {
    try {
      await v2.play();
      v2.pause();
      v2.currentTime = 0;
    } catch (_) {}
  }
  vid1.value?.play().catch(() => {});
});

function onTimeUpdate(e) {
  const src = e.target;
  if (swapping) return;
  const remaining = src.duration - src.currentTime;
  if (isNaN(remaining) || remaining > CROSSFADE) return;

  // Determine which slot is active
  const isVid1 = src === vid1.value;
  const currentSlot = isVid1 ? 0 : 1;
  if (activeSlot.value !== currentSlot) return; // only the active video triggers swap

  swapping = true;
  const next = isVid1 ? vid2.value : vid1.value;
  if (!next) { swapping = false; return; }

  next.currentTime = 0;
  next.play().catch(() => {});
  activeSlot.value = isVid1 ? 1 : 0; // fade in the other one

  // After CSS transition completes, pause+reset the outgoing video
  setTimeout(() => {
    src.pause();
    src.currentTime = 0;
    swapping = false;
  }, CROSSFADE * 1000 + 200);
}
// ────────────────────────────────────────────────────

const formRef = ref(null);
const loading = ref(false);
const errorMsg = ref("");
const form = reactive({ username: "", password: "" });

const rules = {
  username: [{ required: true, message: "请输入用户名", trigger: "blur" }],
  password: [{ required: true, message: "请输入密码", trigger: "blur" }],
};

async function handleLogin() {
  if (!formRef.value) return;
  formRef.value.validate(async (valid) => {
    if (!valid) return;
    loading.value = true;
    errorMsg.value = "";
    try {
      await authStore.login(form.username, form.password);
      const redirect = route.query.redirect || "/";
      router.push(redirect);
    } catch (err) {
      errorMsg.value = err.message || "登录失败，请检查用户名和密码";
    } finally {
      loading.value = false;
    }
  });
}
</script>

<style scoped>
/* ─── Layout ────────────────────────────────────── */
.login-root {
  position: relative;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: #0a0a14; /* fallback */
}

/* ─── Video background (two elements crossfade) ─── */
.login-video-bg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  z-index: 0;
  pointer-events: none;
  opacity: 0;
  transition: opacity 1.5s ease-in-out;
}
.login-video-bg.vid-active {
  opacity: 1;
}

/* ─── Dark overlay ──────────────────────────────── */
.login-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.32);
  z-index: 1;
  pointer-events: none;
}

/* ─── Watermark cover (bottom-right corner) ─────── */
.login-watermark-mask {
  position: absolute;
  bottom: 0;
  right: 0;
  width: 312px;
  height: 104px;
  z-index: 1;
  pointer-events: none;
  background: linear-gradient(
    to top left,
    rgba(10, 10, 20, 1) 0%,
    rgba(10, 10, 20, 0.85) 40%,
    transparent 100%
  );
}

/* ─── Liquid glass card ─────────────────────────── */
.login-card {
  position: relative;
  z-index: 2;
  width: 100%;
  max-width: 420px;
  padding: 48px 40px 44px;
  border-radius: 28px;

  /* Glass fill */
  background: linear-gradient(
    135deg,
    rgba(255, 255, 255, 0.13) 0%,
    rgba(255, 255, 255, 0.06) 100%
  );

  /* Blur + colour boost behind the card */
  backdrop-filter: blur(48px) saturate(180%) brightness(1.08);
  -webkit-backdrop-filter: blur(48px) saturate(180%) brightness(1.08);

  /* Rim lighting — top highlight, bottom secondary glow */
  border: 1px solid rgba(255, 255, 255, 0.22);
  box-shadow:
    inset 0 1.5px 0 rgba(255, 255, 255, 0.50),
    inset 0 -1px 0 rgba(255, 255, 255, 0.10),
    inset 1px 0 0 rgba(255, 255, 255, 0.12),
    0 4px 6px rgba(0, 0, 0, 0.10),
    0 24px 64px rgba(0, 0, 0, 0.40),
    0 0 0 0.5px rgba(255, 255, 255, 0.08);

  color: white;
}


/* ─── Form labels ───────────────────────────────── */
:deep(.glass-form-item .el-form-item__label) {
  color: rgba(255, 255, 255, 0.82) !important;
  font-weight: 500;
}

/* ─── Inputs ────────────────────────────────────── */
:deep(.glass-input .el-input__wrapper) {
  background: rgba(255, 255, 255, 0.06) !important;
  border: 1px solid rgba(255, 255, 255, 0.14) !important;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08) !important;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  transition: background 0.2s, border-color 0.2s;
}

:deep(.glass-input .el-input__wrapper:hover) {
  background: rgba(255, 255, 255, 0.10) !important;
  border-color: rgba(255, 255, 255, 0.24) !important;
}

:deep(.glass-input .el-input__wrapper.is-focus) {
  background: rgba(180, 160, 255, 0.12) !important;
  border-color: rgba(200, 180, 255, 0.50) !important;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.12),
    0 0 0 2px rgba(160, 130, 255, 0.18) !important;
}

:deep(.glass-input .el-input__inner) {
  color: white !important;
  caret-color: white;
}

:deep(.glass-input .el-input__inner::placeholder) {
  color: rgba(255, 255, 255, 0.38);
}

:deep(.glass-input .el-input__prefix-icon),
:deep(.glass-input .el-input__suffix-icon),
:deep(.glass-input .el-icon) {
  color: rgba(255, 255, 255, 0.55) !important;
}

/* ─── Login button ──────────────────────────────── */
.login-btn {
  background: linear-gradient(
    135deg,
    rgba(120, 90, 240, 0.72) 0%,
    rgba(80, 160, 220, 0.72) 100%
  ) !important;
  color: rgba(255, 255, 255, 0.95) !important;
  border: 1px solid rgba(255, 255, 255, 0.22) !important;
  font-weight: 600 !important;
  letter-spacing: 0.08em;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.28),
    0 4px 24px rgba(100, 80, 200, 0.35) !important;
  transition: opacity 0.2s, transform 0.15s !important;
}

.login-btn:hover {
  opacity: 0.88;
  transform: translateY(-1px);
}

.login-btn:active {
  transform: translateY(0);
}

/* ─── Error alert ───────────────────────────────── */
:deep(.glass-alert) {
  background: rgba(245, 80, 80, 0.20) !important;
  border-color: rgba(245, 80, 80, 0.35) !important;
  color: #ffc0c0 !important;
  backdrop-filter: blur(4px);
}

:deep(.glass-alert .el-alert__title) {
  color: #ffc0c0 !important;
}
</style>
