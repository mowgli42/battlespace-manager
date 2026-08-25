import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";

export default defineConfig({
  plugins: [svelte()],
  test: {
    environment: "happy-dom",
  },
  server: {
    host: "0.0.0.0",
    port: 8932,
    proxy: {
      "/api": {
        target: process.env.VITE_API_URL || "http://localhost:8032",
        changeOrigin: true,
      },
    },
  },
  preview: {
    host: "0.0.0.0",
    port: 8932,
    proxy: {
      "/api": {
        target: process.env.VITE_API_URL || "http://localhost:8032",
        changeOrigin: true,
      },
    },
  },
});
