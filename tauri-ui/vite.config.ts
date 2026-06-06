import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../boss_tauri/frontend",
    emptyOutDir: true,
  },
  server: {
    port: 1420,
    strictPort: true,
  },
});
