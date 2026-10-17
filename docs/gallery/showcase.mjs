#!/usr/bin/env node
/**
 * Worlds screenshot gallery: the showcase images the main README uses.
 *
 * Takes pictures already in docs/gallery/shots/ and frames them: a rounded
 * window (or phone) on a soft starry background, with one of the crew
 * peeking in. Text stays in the README (the images carry no words), so
 * captions stay searchable and readable by screen readers.
 *
 * Usage (from ui/, after capture.mjs):
 *   node ../docs/gallery/showcase.mjs
 * Writes docs/gallery/showcase/<name>.png.
 */
import { createRequire } from "node:module";
import { readFileSync, mkdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, "..", "..");
const uiDir = join(repo, "ui");
const out = join(here, "showcase");
const require = createRequire(join(uiDir, "package.json"));
const { chromium } = require("playwright");

const shot = (id, file) => join(here, "shots", id, file);
const art = (name) => join(uiDir, "public", "assets", "crew", "512", `${name}.webp`);
const data = (file) => {
  const type = file.endsWith(".webp") ? "image/webp" : "image/png";
  return `data:${type};base64,${readFileSync(file).toString("base64")}`;
};

const BG = {
  night: "radial-gradient(120% 90% at 15% 10%, #3a2f6b 0%, #1d2146 45%, #12152a 100%)",
  dusk: "radial-gradient(120% 90% at 85% 10%, #5a3560 0%, #242447 50%, #12152a 100%)",
  sea: "radial-gradient(120% 90% at 20% 90%, #1f4d5c 0%, #1b2447 50%, #12152a 100%)",
};

// A few soft stars, placed the same way every run.
function stars(w, h, n = 34, seed = 7) {
  let s = seed;
  const rnd = () => ((s = (s * 9301 + 49297) % 233280) / 233280);
  let out = "";
  for (let i = 0; i < n; i++) {
    const size = rnd() < 0.15 ? 3 : rnd() < 0.5 ? 2 : 1.5;
    out += `<i style="position:absolute;left:${(rnd() * w).toFixed(0)}px;top:${(rnd() * h).toFixed(0)}px;width:${size}px;height:${size}px;border-radius:50%;background:#f3e7c9;opacity:${(0.35 + rnd() * 0.5).toFixed(2)}"></i>`;
  }
  // two twinkles
  out += `<b style="position:absolute;left:${(w * 0.88).toFixed(0)}px;top:${(h * 0.12).toFixed(0)}px;color:#f1c98a;font-size:22px">✦</b>`;
  out += `<b style="position:absolute;left:${(w * 0.06).toFixed(0)}px;top:${(h * 0.8).toFixed(0)}px;color:#b9a7f0;font-size:16px">✦</b>`;
  return out;
}

const windowFrame = (src, w, h, cropH) => `
  <div style="width:${w}px;border-radius:18px;overflow:hidden;background:#0e1124;box-shadow:0 24px 60px rgba(5,6,20,.55),0 0 0 1px rgba(236,228,214,.14)">
    <div style="height:34px;display:flex;align-items:center;gap:8px;padding:0 14px;background:#1a1d38">
      <i style="width:11px;height:11px;border-radius:50%;background:#e7a3b0"></i>
      <i style="width:11px;height:11px;border-radius:50%;background:#e2ab62"></i>
      <i style="width:11px;height:11px;border-radius:50%;background:#9cc48a"></i>
      <span style="margin-left:14px;flex:1;height:18px;border-radius:9px;background:#12152a"></span>
    </div>
    <div style="height:${cropH ?? h}px;overflow:hidden"><img src="${src}" style="display:block;width:${w}px"></div>
  </div>`;

const phoneFrame = (src, w, h) => `
  <div style="width:${w}px;height:${h}px;border-radius:34px;padding:9px;background:#0b0d1c;box-shadow:0 24px 50px rgba(5,6,20,.6),0 0 0 1px rgba(236,228,214,.18);box-sizing:border-box">
    <div style="width:100%;height:100%;border-radius:26px;overflow:hidden;position:relative">
      <img src="${src}" style="display:block;width:100%">
    </div>
  </div>`;

const peek = (name, css) =>
  `<img src="${data(art(name))}" style="position:absolute;${css};filter:drop-shadow(0 10px 18px rgba(5,6,20,.55))">`;

function canvas(w, h, bg, inner) {
  return `<!doctype html><html><body style="margin:0"><div id="c" style="position:relative;width:${w}px;height:${h}px;overflow:hidden;background:${bg};font-family:system-ui">${stars(w, h)}${inner}</div></body></html>`;
}

const jobs = [];

// Hero: the Bridge on desktop with the phone beside it, and the Assistant waving.
jobs.push([
  "hero",
  1600,
  900,
  canvas(1600, 900, BG.night, `
    <div style="position:absolute;left:240px;top:90px">${windowFrame(data(shot("bridge", "starfield-1440.png")), 1060, 0, 680)}</div>
    <div style="position:absolute;left:1230px;top:240px">${phoneFrame(data(shot("bridge", "starfield-390.png")), 300, 620)}</div>
    ${peek("assistant-hello", "left:18px;top:560px;width:215px")}
    ${peek("sol-hello", "left:1400px;top:40px;width:140px")}
  `),
]);

// Cards: one screen each, framed, with a crew member peeking in.
const cards = [
  ["room-drawer", "room-drawer-studio", "starfield-1440.png", BG.dusk, "assistant-listening", "right:26px;bottom:18px;width:150px"],
  ["secrets", "secrets-waiting", "starfield-1440.png", BG.night, "sol-curious", "right:24px;bottom:22px;width:130px"],
  ["ask-in-chat", "ask-in-chat", "starfield-1440.png", BG.sea, "assistant-hello", "right:20px;bottom:10px;width:140px"],
  ["crew", "crew", "starfield-1440.png", BG.dusk, "renai-hello", "right:20px;bottom:0;width:150px"],
  ["find-a-room", "find-a-room", "starfield-1440.png", BG.sea, "sol-cheer", "right:24px;bottom:22px;width:130px"],
  ["first-light", "first-light-companion", "starfield-1440.png", BG.night, "sol-rest", "right:24px;bottom:22px;width:130px"],
];
for (const [name, id, file, bg, who, whoCss] of cards) {
  jobs.push([
    name,
    800,
    520,
    canvas(800, 520, bg, `
      <div style="position:absolute;left:40px;top:40px">${windowFrame(data(shot(id, file)), 640, 0, 400)}</div>
      ${peek(who, whoCss)}
    `),
  ]);
}

// Themes: the Bridge on a phone in every theme, side by side.
const themes = ["starfield", "doorways", "station", "moss", "ocean", "plain"];
jobs.push([
  "themes",
  1600,
  600,
  canvas(1600, 600, BG.night, `
    <div style="position:absolute;left:50px;top:60px;display:flex;gap:22px">
      ${themes.map((t) => phoneFrame(data(shot("bridge", `${t}-390.png`)), 220, 470)).join("")}
    </div>
    ${peek("sol-cheer", "right:16px;bottom:24px;width:110px")}
  `),
]);

mkdirSync(out, { recursive: true });
const browser = await chromium.launch();
try {
  for (const [name, w, h, html] of jobs) {
    const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
    await page.setContent(html, { waitUntil: "load" });
    await page.locator("#c").screenshot({ path: join(out, `${name}.png`) });
    console.log(`ok   docs/gallery/showcase/${name}.png`);
    await page.close();
  }
} finally {
  await browser.close();
}
