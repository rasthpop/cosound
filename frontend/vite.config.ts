import { fileURLToPath, URL } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// API_PROXY_TARGET=http://127.0.0.1:8000 proxies /api to a running backend in dev.
const apiTarget = process.env.API_PROXY_TARGET;

export default defineConfig({
  plugins: [react()],
  server: apiTarget ? { proxy: { "/api": { target: apiTarget, changeOrigin: true } } } : {},
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}", "test/**/*.test.{ts,tsx}"],
    exclude: ["e2e/**", "node_modules/**"],
  },
});
