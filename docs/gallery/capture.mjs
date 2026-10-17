#!/usr/bin/env node
/**
 * Worlds screenshot gallery: capture.
 *
 * Reads docs/gallery/manifest.json, opens each screen of the production
 * preview build against the deterministic mock API (ui/scripts/e2e-api.mjs,
 * the same fixture the e2e suite uses), and writes
 *   docs/gallery/shots/<id>/<theme>-<width>.png
 * then marks each entry captured (with the date and commit) and regenerates
 * the table in docs/gallery/README.md between the gallery markers.
 *
 * Never point this at a real Worlds: the repo is public, and screenshots of
 * a real instance would publish real data.
 *
 * Usage (from ui/, after `npm run build`):
 *   node ../docs/gallery/capture.mjs                 # everything capturable
 *   node ../docs/gallery/capture.mjs --only bridge   # one entry
 *   node ../docs/gallery/capture.mjs --all-themes    # every theme, every entry
 *   node ../docs/gallery/capture.mjs --table-only    # just rebuild README table
 *
 * Entries with a "path" (server-rendered pages like /setup and /login) are
 * skipped: the preview build doesn't serve them. capture-server.mjs takes
 * those from a throwaway local Worlds.
 *
 * An entry may also carry "fixture" (a made-up data variant: "many-rooms",
 * "no-rooms"), "steps" ({click: {role, name}} or {fill: {label, value}}) and
 * "scroll_to" ({role, name}) to show a particular state.
 */
import { spawn, execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, "..", "..");
const uiDir = join(repo, "ui");
const manifestPath = join(here, "manifest.json");
const readmePath = join(here, "README.md");
const shotsDir = join(here, "shots");

const args = process.argv.slice(2);
const only = args.includes("--only") ? args[args.indexOf("--only") + 1] : null;
const allThemes = args.includes("--all-themes");
const tableOnly = args.includes("--table-only");

const THEME_STORAGE_KEY = "pw-station-theme"; // ui/src/app/prefs-dom.ts
const API_PORT = 4174; // ui/scripts/e2e-api.mjs
const UI_PORT = Number(process.env.GALLERY_UI_PORT ?? 4183);

const manifest = JSON.parse(readFileSync(manifestPath, "utf-8"));

function shotPath(id, theme, width) {
  return join(shotsDir, id, `${theme}-${width}.png`);
}

function renderTable() {
  const rows = manifest.entries.map((e) => {
    const themes = e.themes ?? manifest.defaults.themes;
    const widths = e.widths ?? manifest.defaults.widths;
    const cells = widths.map((w) => {
      const file = shotPath(e.id, themes[0], w);
      if (!existsSync(file)) return "not yet";
      const rel = relative(here, file);
      return `[![${e.alt} (${w}px)](${rel})](${rel})`;
    });
    const more =
      themes.length > 1
        ? ` Other themes: ${themes
            .slice(1)
            .map((t) => (existsSync(shotPath(e.id, t, widths[0])) ? `[${t}](${relative(here, shotPath(e.id, t, widths[0]))})` : t))
            .join(", ")}.`
        : "";
    const state = e.status === "captured" ? `captured ${e.captured_at ?? ""} @ ${e.commit ?? "?"}` : e.status;
    return `| **${e.title}**<br>${e.caption}${more} | ${cells.join(" | ")} | ${state} |`;
  });
  const widths = manifest.defaults.widths;
  const head = `| Screen | ${widths.map((w) => `${w}px`).join(" | ")} | State |\n|---|${widths.map(() => "---").join("|")}|---|`;
  return `${head}\n${rows.join("\n")}`;
}

function writeReadmeTable() {
  const readme = readFileSync(readmePath, "utf-8");
  const start = "<!-- gallery:start -->";
  const end = "<!-- gallery:end -->";
  const a = readme.indexOf(start);
  const b = readme.indexOf(end);
  if (a < 0 || b < a) throw new Error("README.md is missing the gallery markers");
  const next = `${readme.slice(0, a + start.length)}\n${renderTable()}\n${readme.slice(b)}`;
  writeFileSync(readmePath, next);
}

async function portInUse(port) {
  try {
    await fetch(`http://127.0.0.1:${port}/`, { signal: AbortSignal.timeout(1000) });
    return true;
  } catch {
    return false;
  }
}

async function waitFor(url, ms = 60_000) {
  const until = Date.now() + ms;
  while (Date.now() < until) {
    try {
      const r = await fetch(url);
      if (r.ok || r.status < 500) return;
    } catch {
      /* not up yet */
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`timed out waiting for ${url}`);
}

// Data variants for states the standard mock world doesn't show. They
// rewrite only the browser's copy of GET /api/rooms, with made-up rooms.
const EXTRA_ROOMS = [
  "Atelier", "Bakery", "Boathouse", "Conservatory", "Darkroom", "Greenhouse",
  "Kiln", "Loft", "Observatory", "Pantry", "Stables", "Tinker Shop",
];

async function applyFixture(page, fixture) {
  await page.route("**/api/rooms", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    const rows = Array.isArray(body.data) ? body.data : [];
    if (fixture === "no-rooms") {
      body.data = [];
    } else if (fixture === "many-rooms") {
      const template = rows.find((r) => r.status === "healthy") ?? rows[0];
      body.data = rows.concat(
        EXTRA_ROOMS.map((name) => {
          const id = name.toLowerCase().replace(/[^a-z0-9]+/g, "-");
          return {
            ...template,
            id,
            base_url: `https://${id}.room.test`,
            public_url: null,
            status: "healthy",
            room: { ...template.room, id, name, status: "healthy" },
            needs_you: [],
            cards: [],
            keeper: null,
            doorway: null,
          };
        }),
      );
    } else {
      throw new Error(`unknown fixture ${fixture}`);
    }
    await route.fulfill({ response, json: body });
  });
}

async function main() {
  if (tableOnly) {
    writeReadmeTable();
    console.log("gallery table rebuilt");
    return;
  }
  if (!existsSync(join(uiDir, "dist", "index.html"))) {
    throw new Error("ui/dist is missing: run `npm run build` in ui/ first");
  }
  const require = createRequire(join(uiDir, "package.json"));
  const { chromium } = require("playwright");

  // Never reuse a server someone else left running: it may serve another
  // checkout's build, and the pictures would silently be of the wrong app.
  for (const port of [API_PORT, UI_PORT]) {
    if (await portInUse(port)) {
      throw new Error(`port ${port} is already in use; stop that server first (or set GALLERY_UI_PORT)`);
    }
  }
  const children = [];
  const start = (cmdArgs, env = {}) => {
    // node + the script directly (no npx wrapper) in its own process group,
    // so stopping it stops everything it started.
    const child = spawn(process.execPath, cmdArgs, {
      cwd: uiDir,
      env: { ...process.env, ...env },
      stdio: "ignore",
      detached: true,
    });
    children.push(child);
    return child;
  };
  start(["scripts/e2e-api.mjs"]);
  start([join(uiDir, "node_modules", "vite", "bin", "vite.js"), "preview", "--port", String(UI_PORT), "--strictPort", "--host", "127.0.0.1"], {
    VITE_API_PROXY_TARGET: `http://127.0.0.1:${API_PORT}`,
  });

  let commit = "unknown";
  try {
    commit = execFileSync("git", ["rev-parse", "--short", "HEAD"], { cwd: repo, encoding: "utf-8" }).trim();
  } catch {
    /* not a git checkout */
  }
  const today = new Date().toISOString().slice(0, 10);

  try {
    await waitFor(`http://127.0.0.1:${API_PORT}/healthz`);
    await waitFor(`http://127.0.0.1:${UI_PORT}/`);
    const browser = await chromium.launch();
    for (const entry of manifest.entries) {
      if (only && entry.id !== only) continue;
      if (entry.path) {
        console.log(`skip ${entry.id}: server-rendered (${entry.path}); use capture-server.mjs`);
        continue;
      }
      const themes = allThemes ? manifest.all_themes : (entry.themes ?? manifest.defaults.themes);
      const widths = entry.widths ?? manifest.defaults.widths;
      let ok = true;
      for (const theme of themes) {
        for (const width of widths) {
          const context = await browser.newContext({ viewport: { width, height: width < 600 ? 844 : 1000 } });
          await context.addInitScript(
            ([key, value]) => {
              try {
                window.localStorage.setItem(key, value);
              } catch {
                /* storage blocked: the default theme shows */
              }
            },
            [THEME_STORAGE_KEY, theme],
          );
          const page = await context.newPage();
          if (entry.fixture) await applyFixture(page, entry.fixture);
          try {
            await page.goto(`http://127.0.0.1:${UI_PORT}/`);
            if (entry.area) {
              await page
                .getByRole("navigation", { name: "World navigation" })
                .getByRole("button", { name: entry.area })
                .click();
            }
            for (const step of entry.steps ?? []) {
              if (step.click) await page.getByRole(step.click.role, { name: step.click.name }).first().click();
              if (step.fill) await page.getByLabel(step.fill.label).first().fill(step.fill.value);
            }
            await page.waitForLoadState("networkidle");
            // Start every picture at the top of the page: a click can leave
            // the page scrolled to wherever the button was. An entry can then
            // name the part it is about ("scroll_to"), which is brought into view.
            await page.evaluate(() => window.scrollTo(0, 0));
            if (entry.scroll_to) {
              await page
                .getByRole(entry.scroll_to.role, { name: entry.scroll_to.name })
                .first()
                .evaluate((el) => el.scrollIntoView({ block: "start" }));
            }
            await page.waitForTimeout(400);
            const file = shotPath(entry.id, theme, width);
            mkdirSync(dirname(file), { recursive: true });
            await page.screenshot({ path: file, fullPage: false });
            console.log(`ok   ${relative(repo, file)}`);
          } catch (err) {
            ok = false;
            console.log(`FAIL ${entry.id} ${theme} ${width}: ${String(err).split("\n")[0]}`);
          } finally {
            await context.close();
          }
        }
      }
      if (ok) {
        entry.status = "captured";
        entry.captured_at = today;
        entry.commit = commit;
      }
    }
    await browser.close();
  } finally {
    for (const child of children) {
      try {
        process.kill(-child.pid, "SIGTERM");
      } catch {
        /* already gone */
      }
    }
  }
  writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
  writeReadmeTable();
}

main().catch((err) => {
  console.error(String(err));
  process.exit(1);
});
