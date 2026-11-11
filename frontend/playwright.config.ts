import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:8765",
    channel: process.env.HEALTH_TEST_BROWSER || undefined,
    viewport: { width: 1440, height: 1000 },
  },
  webServer: {
    command: "python ../scripts/serve_test.py",
    url: "http://127.0.0.1:8765/api/v1/health",
    reuseExistingServer: false,
    gracefulShutdown: { signal: "SIGTERM", timeout: 3000 },
  },
});
