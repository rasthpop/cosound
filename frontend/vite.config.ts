import { rm } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath, URL } from "node:url";

import { storybookTest } from "@storybook/addon-vitest/vitest-plugin";
import tailwindcss from "@tailwindcss/vite";
import { playwright } from "@vitest/browser-playwright";
import react from "@vitejs/plugin-react";
import type { Plugin } from "vite";
import { defineConfig } from "vitest/config";

// API_PROXY_TARGET=http://127.0.0.1:8000 proxies /api to a running backend in dev.
const apiTarget = process.env.API_PROXY_TARGET;

/** `public/mockServiceWorker.js` serves MSW in mock mode only; production builds drop it. */
function dropMockWorker(): Plugin {
  let outDir = "dist";
  let mock = false;
  return {
    name: "drop-mock-worker",
    apply: "build",
    configResolved(config) {
      outDir = config.build.outDir;
      mock = config.mode === "mock";
    },
    async closeBundle() {
      if (!mock) await rm(join(outDir, "mockServiceWorker.js"), { force: true });
    },
  };
}

export default defineConfig({
  plugins: [react(), tailwindcss(), dropMockWorker()],
  server: apiTarget ? { proxy: { "/api": { target: apiTarget, changeOrigin: true } } } : {},
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  // pre-bundled up front so the first story-test run does not reload mid-run
  optimizeDeps: { include: ["msw-storybook-addon/csf3"] },
  test: {
    projects: [
      {
        extends: true,
        test: {
          name: "unit",
          environment: "jsdom",
          setupFiles: ["./test/setup.ts"],
          include: ["src/**/*.test.{ts,tsx}", "test/**/*.test.{ts,tsx}"],
          exclude: ["e2e/**", "node_modules/**"],
        },
      },
      {
        // every story as a browser test, with axe (npm run test-storybook)
        extends: true,
        plugins: [storybookTest({ configDir: fileURLToPath(new URL("./.storybook", import.meta.url)) })],
        test: {
          name: "storybook",
          browser: {
            enabled: true,
            headless: true,
            provider: playwright(),
            instances: [{ browser: "chromium" }],
          },
        },
      },
    ],
  },
});
