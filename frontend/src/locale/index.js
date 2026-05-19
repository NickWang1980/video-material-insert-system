import { createI18n } from "vue-i18n";

import ttsZhCN from "./zh-CN/tts.json";
import ttsEnUS from "./en-US/tts.json";
import copyGenZhCN from "./zh-CN/copyGen.json";
import copyGenEnUS from "./en-US/copyGen.json";

const STORAGE_KEY = "vmis_tts_locale";

function _initialLocale() {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    if (v === "zh-CN" || v === "en-US") return v;
  } catch {
    // ignore
  }
  return "zh-CN";
}

const messages = {
  "zh-CN": { tts: ttsZhCN, copyGen: copyGenZhCN },
  "en-US": { tts: ttsEnUS, copyGen: copyGenEnUS },
};

export const i18n = createI18n({
  legacy: false,
  globalInjection: true,
  locale: _initialLocale(),
  fallbackLocale: "zh-CN",
  messages,
  missingWarn: false,
  fallbackWarn: false,
});

export function setLocale(locale) {
  if (locale !== "zh-CN" && locale !== "en-US") return;
  i18n.global.locale.value = locale;
  try {
    localStorage.setItem(STORAGE_KEY, locale);
  } catch {
    // ignore
  }
}

export function toggleLocale() {
  const current = i18n.global.locale.value;
  setLocale(current === "zh-CN" ? "en-US" : "zh-CN");
}

export default i18n;
