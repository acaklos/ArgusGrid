import { defineConfig } from "@playwright/test";

// End-to-end tests run against the REAL backend and database (started by devtools/e2e.ps1).
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  workers: 1,
  fullyParallel: false,
  reporter: [["list"], ["json", { outputFile: "e2e/results/report.json" }]],
  outputDir: "e2e/results/artifacts",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://127.0.0.1:8000",
    screenshot: "only-on-failure",
    trace: "off",
  },
  projects: [{ name: "chromium", use: { browserName: "chromium", viewport: { width: 1280, height: 800 } } }],
});
