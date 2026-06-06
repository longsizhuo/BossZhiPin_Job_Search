import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../src/boss_zhipin/tauri/frontend",
    emptyOutDir: true,
  },
  server: {
    port: 1420,
    strictPort: true,
  },
});
