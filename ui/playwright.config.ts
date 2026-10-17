import { defineConfig } from "@playwright/test";

/**
 * Playwright config for the front-door UI (the default: `npx playwright test`).
 *
 *  - e2e-fd/       mocked API (page.route from src/fd/fixtures.ts), Vite dev server on 4180. No backend.
 *  - e2e-fd-live/  the REAL read API (`python -m personal_world.worlds.dev`, seeded reference provider)
 *                  through the Vite proxy on 4181. Use 127.0.0.1, never localhost: TrustedHost is strict.
 *
 * Phone (390) and desktop (1280) are both first-class. A hung test fails fast: 30s per test, 8 minutes total.
 * Screenshots: PW_FD_SHOTS=<dir>.
 */
const MOCK_PORT = Number(process.env.PW_FD_PORT ?? 4180);
const LIVE_PORT = Number(process.env.PW_FD_LIVE_PORT ?? 4181);
const API_PORT = 8765;
const phone = { viewport: { width: 390, height: 844 }, hasTouch: true };
const desktop = { viewport: { width: 1280, height: 800 } };

export default defineConfig({
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  timeout: 30_000,
  expect: { timeout: 7_000 },
  globalTimeout: 8 * 60_000,
  projects: [
    { name: "phone-390", testDir: "./e2e-fd", use: { ...phone, baseURL: `http://127.0.0.1:${MOCK_PORT}` } },
    { name: "desktop-1280", testDir: "./e2e-fd", use: { ...desktop, baseURL: `http://127.0.0.1:${MOCK_PORT}` } },
    { name: "live-phone-390", testDir: "./e2e-fd-live", use: { ...phone, baseURL: `http://127.0.0.1:${LIVE_PORT}` } },
    { name: "live-desktop-1280", testDir: "./e2e-fd-live", use: { ...desktop, baseURL: `http://127.0.0.1:${LIVE_PORT}` } },
  ],
  webServer: [
    { command: `npx vite --port ${MOCK_PORT} --strictPort --host 127.0.0.1`, url: `http://127.0.0.1:${MOCK_PORT}`, reuseExistingServer: !process.env.CI, timeout: 60_000 },
    { command: "cd .. && uv run python -m personal_world.worlds.dev", url: `http://127.0.0.1:${API_PORT}/api/boards/home`, reuseExistingServer: !process.env.CI, timeout: 90_000 },
    { command: `npx vite --port ${LIVE_PORT} --strictPort --host 127.0.0.1`, url: `http://127.0.0.1:${LIVE_PORT}`, env: { VITE_API_PROXY_TARGET: `http://127.0.0.1:${API_PORT}` }, reuseExistingServer: !process.env.CI, timeout: 60_000 },
  ],
});
