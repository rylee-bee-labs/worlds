import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright config for the Worlds kit preview (e2e-kit/*.spec.ts).
 *
 * The kit is a static artifact — dist-kit/ — with no app and no API, so this
 * config is deliberately standalone: it boots ONLY the static kit server
 * (scripts/serve-kit.mjs) and points the browser at preview.html. That lets
 * the kit's accessibility floor be verified without building the app.
 *
 *   npm run kit:build && npm run kit:test:e2e
 *
 * It reuses the repo's real Playwright + @axe-core/playwright toolchain and
 * the focus-ring helpers in e2e/helpers.ts; only the servers differ.
 */
const KIT_PORT = Number(process.env.PW_E2E_KIT_PORT ?? 4175);

export default defineConfig({
  testDir: "./e2e-kit",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: `http://127.0.0.1:${KIT_PORT}`,
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "kit",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      command: "node scripts/serve-kit.mjs",
      url: `http://127.0.0.1:${KIT_PORT}/preview.html`,
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
  ],
});