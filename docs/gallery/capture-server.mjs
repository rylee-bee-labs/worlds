#!/usr/bin/env node
/**
 * Worlds screenshot gallery: the server-rendered pages (First Light and
 * sign-in), which the preview build used by capture.mjs doesn't serve.
 *
 * Point it at a THROWAWAY local Worlds started with empty data and config
 * directories and a made-up PW_API_TOKEN. It walks First Light, photographs
 * the steps, finishes setup (so the instance is used up), then photographs
 * the sign-in page. It refuses any address that isn't this machine.
 *
 * Usage (from ui/):
 *   node ../docs/gallery/capture-server.mjs --base http://127.0.0.1:8791
 *
 * Starting the throwaway Worlds (from the repo root, fresh dirs every time).
 * Build the app first (bash scripts/build-app.sh): First Light's companion
 * pictures are served from it, and without it they show as empty circles.
 *   PW_DATA_DIR=$(mktemp -d) PW_CONFIG_DIR=$(mktemp -d) PW_API_TOKEN=made-up \
 *     uv run uvicorn personal_world.api:create_app --factory --port 8791
 */
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, "..", "..");
const uiDir = join(repo, "ui");
const manifestPath = join(here, "manifest.json");

const args = process.argv.slice(2);
const base = args.includes("--base") ? args[args.indexOf("--base") + 1] : null;
if (!base) throw new Error("pass --base http://127.0.0.1:<port> (a throwaway local Worlds)");
const host = new URL(base).hostname;
if (!["127.0.0.1", "localhost", "[::1]", "::1"].includes(host)) {
  throw new Error(`refusing ${host}: only a throwaway Worlds on this machine may be photographed`);
}

const manifest = JSON.parse(readFileSync(manifestPath, "utf-8"));
const widths = manifest.defaults.widths;
const theme = manifest.defaults.themes[0];
const require = createRequire(join(uiDir, "package.json"));
const { chromium } = require("playwright");

let commit = "unknown";
try {
  commit = execFileSync("git", ["rev-parse", "--short", "HEAD"], { cwd: repo, encoding: "utf-8" }).trim();
} catch {
  /* not a git checkout */
}
const today = new Date().toISOString().slice(0, 10);
const done = new Set();

async function shoot(page, id, width) {
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(300);
  const file = join(here, "shots", id, `${theme}-${width}.png`);
  mkdirSync(dirname(file), { recursive: true });
  await page.screenshot({ path: file, fullPage: false });
  console.log(`ok   ${relative(repo, file)}`);
  done.add(id);
}

const visible = (page, headingId) => page.locator(`#${headingId}`).waitFor({ state: "visible" });

const browser = await chromium.launch();
try {
  // Walk First Light at each width without finishing, then finish once.
  for (const [i, width] of widths.entries()) {
    const last = i === widths.length - 1;
    const context = await browser.newContext({ viewport: { width, height: width < 600 ? 844 : 1000 } });
    const page = await context.newPage();
    await page.goto(`${base}/setup`);
    await visible(page, "h-welcome");
    await shoot(page, "first-light", width);
    await page.click("#btn-start");
    await visible(page, "h-auth");
    await page.click("#btn-auth-next");
    await visible(page, "h-comfort");
    await shoot(page, "first-light-comfort", width);
    await page.click("#btn-comfort-next");
    await visible(page, "h-companion");
    await shoot(page, "first-light-companion", width);
    if (last) {
      await page.click("#btn-companion-next");
      await visible(page, "h-finish");
      await page.click("#btn-finish");
      await page.waitForLoadState("networkidle");
    }
    await context.close();
  }
  for (const width of widths) {
    const context = await browser.newContext({ viewport: { width, height: width < 600 ? 844 : 1000 } });
    const page = await context.newPage();
    await page.goto(`${base}/login`);
    await page.waitForLoadState("networkidle");
    if (!new URL(page.url()).pathname.startsWith("/login")) {
      throw new Error(`expected the sign-in page, got ${page.url()} (is setup finished?)`);
    }
    await shoot(page, "login", width);
    await context.close();
  }
} finally {
  await browser.close();
}

for (const entry of manifest.entries) {
  if (done.has(entry.id)) {
    entry.status = "captured";
    entry.captured_at = today;
    entry.commit = commit;
  }
}
writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
console.log("now run: node ../docs/gallery/capture.mjs --table-only");
