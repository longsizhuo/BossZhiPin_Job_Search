import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    // 必须指向 Python 包内 Tauri.toml 的 frontendDist（"./frontend" 相对
    // src/boss_zhipin/tauri/ 解析）。包目录挪了这里要同步改，否则前端构建
    // 进死目录、Tauri 静默加载旧 bundle。
    outDir: "../src/boss_zhipin/tauri/frontend",
    emptyOutDir: true,
  },
  server: {
    port: 1420,
    strictPort: true,
  },
});
