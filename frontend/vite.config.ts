import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// The API listens on loopback in development; the dev server proxies /api so cookies stay same-origin.
export default defineConfig({
  plugins: [react()],
  // The built files must not live under /assets: that path is a page of the application.
  build: {
    assetsDir: "static",
    rollupOptions: {
      output: { manualChunks: { cytoscape: ["cytoscape"], leaflet: ["leaflet"] } },
    },
  },
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: false } },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
