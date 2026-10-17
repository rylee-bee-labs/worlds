#!/usr/bin/env node

/**
 * serve-kit.mjs — a tiny static server for the built Worlds kit (ui/dist-kit/).
 *
 * It exists so the kit preview can be gated by Playwright exactly like the
 * app is, without building or booting the app: the kit is a static artifact.
 * Point a browser at /preview.html.
 *
 *   node scripts/serve-kit.mjs            # 4175 (override PW_E2E_KIT_PORT)
 */

import { createServer } from "node:http";
import { existsSync, readFileSync, statSync } from "node:fs";
import { dirname, extname, join, normalize, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = resolve(__dirname, "..", "dist-kit");
const port = Number(process.env.PW_E2E_KIT_PORT ?? 4175);

const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".md": "text/markdown; charset=utf-8",
  ".woff2": "font/woff2",
  ".svg": "image/svg+xml",
};

createServer((req, res) => {
  const urlPath = decodeURIComponent((req.url ?? "/").split("?")[0]);
  const rel = urlPath === "/" ? "preview.html" : urlPath.replace(/^\/+/, "");
  const file = normalize(join(root, rel));
  if (!file.startsWith(root + sep) || !existsSync(file) || statSync(file).isDirectory()) {
    res.writeHead(404, { "content-type": "text/plain; charset=utf-8" });
    res.end("not found");
    return;
  }
  res.writeHead(200, { "content-type": TYPES[extname(file)] ?? "application/octet-stream" });
  res.end(readFileSync(file));
}).listen(port, "127.0.0.1", () => {
  console.log(`kit preview → http://127.0.0.1:${port}/preview.html`);
});