import { defineConfig, devices } from "@playwright/test";

// Mock mode by default (MSW in the browser). E2E_REAL_BACKEND=1 runs the dev server against a
// live API instead: set API_PROXY_TARGET (e.g. http://127.0.0.1:8000) and start the backend.
const realBackend = process.env.E2E_REAL_BACKEND === "1";
const port = 5174;

export default defineConfig({
  testDir: "e2e",
  timeout: realBackend ? 120_000 : 30_000,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: { baseURL: `http://localhost:${port}`, trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: realBackend
      ? `npx vite --port ${port} --strictPort`
      : `npx vite --mode mock --port ${port} --strictPort`,
    url: `http://localhost:${port}`,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
