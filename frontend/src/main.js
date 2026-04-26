import { createApp } from "vue";
import { createPinia } from "pinia";
import ElementPlus from "element-plus";
import "element-plus/dist/index.css";

import router from "./router";
import App from "./App.vue";

import "./assets/styles/global.css";

const app = createApp(App);
app.use(createPinia());
app.use(router);
app.use(ElementPlus);

// Mount only after initial navigation resolves so App.vue never renders
// with route.name === undefined (which causes white app-shell flash).
router.isReady().then(() => app.mount("#app"));
