import { defineConfig, devices } from "@playwright/test";

/**
 * UAT walk: the real Worlds, as its owner, with every change blocked.
 *
 * The e2e suite (playwright.config.ts) proves screens against a fixture
 * API. That can't catch what only real data and real deploys do (seven
 * needs where fixtures have two; an old page after a deploy). This walk
 * visits a LIVE Worlds instead, read-only:
 *   - every non-GET request to /api is aborted and recorded ("would have
 *     sent"), so nothing is answered, saved or deleted;
 *   - it signs in with a bearer token from PW_UAT_TOKEN (never written
 *     anywhere by this suite; the runner passes it in memory). Use a
 *     read-only viewer token (POST /api/identity/viewers, owner + step-up):
 *     it acts as the owner for reads only and can never write or elevate,
 *     so person-only screens load without handing the walk owner power.
 *     In Memory and Chat it sees structure only (record category names and
 *     counts; chat entries as when/who, no text); journal entries, record
 *     contents, memory search, recall and message bodies answer 403.
 *     See docs/IDENTITY-BOUNDARY.md ("Read-only viewer credential");
 *   - it writes findings (JSON + Markdown) and screenshots under
 *     PW_UAT_OUT, which stays on the machine that ran it.
 *
 *   PW_UAT_URL=https://… PW_UAT_TOKEN=… PW_UAT_OUT=/tmp/uat npx playwright test -c playwright.uat.config.ts
 *
 * There is no webServer: it only ever talks to the URL it's given.
 */
const url = process.env.PW_UAT_URL;
const token = process.env.PW_UAT_TOKEN;
if (!url || !token) throw new Error("PW_UAT_URL and PW_UAT_TOKEN are required");

export default defineConfig({
  testDir: "./uat",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 5 * 60_000,
  reporter: "list",
  use: {
    baseURL: url,
    ignoreHTTPSErrors: true,
    extraHTTPHeaders: { Authorization: `Bearer ${token}` },
    trace: "off",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
    {
      name: "phone",
      use: { ...devices["Desktop Chrome"], viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true },
    },
  ],
});
