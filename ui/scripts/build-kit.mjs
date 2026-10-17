#!/usr/bin/env node

/**
 * build-kit.mjs
 *
 * Builds the "Worlds kit" — the exportable, framework-free Worlds design
 * language — into ui/dist-kit/, ready for other tool UIs to vendor.
 *
 *   dist-kit/
 *     tokens.css    the generated tokens (all themes) — copied verbatim
 *     base.css      the kit's plain CSS (copied from kit/src/base.css)
 *     fonts/        only the .woff2 faces base.css actually loads
 *     kit.json      provenance: name, version, built_at, themes
 *     README.md     how to vendor + use it
 *     preview.html  every component, every variant, all themes
 *
 * Reproducible by design: `version` is kit/VERSION plus a hash of the shipped
 * files, so a rebuild of unchanged sources is byte-identical at any commit —
 * which is what `kit:check` (scripts/check-kit.mjs) relies on.
 *
 * Usage:
 *   node scripts/build-kit.mjs          # also regenerates tokens first
 *   SOURCE_DATE_EPOCH=… node scripts/build-kit.mjs
 */

import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, resolve, basename } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const uiDir = resolve(__dirname, "..");
const repoRoot = resolve(uiDir, "..");
const kitSrcDir = resolve(uiDir, "kit");
const themesDir = resolve(repoRoot, "design/themes");
const fontsDir = resolve(uiDir, "public/assets/fonts");
const generatedCss = resolve(uiDir, "src/generated/tokens.css");
const outDir = resolve(uiDir, "dist-kit");

// ── Provenance ────────────────────────────────────────────────────────────

// `version` is content-addressed: the kit's semver (kit/VERSION) plus a hash
// of what it ships. Unrelated commits never change it, so a committed
// dist-kit/ stays in sync until the kit itself changes. `built_at` is only
// recorded when SOURCE_DATE_EPOCH is set; otherwise the hash is the identity.
const semver = readFileSync(resolve(kitSrcDir, "VERSION"), "utf-8").trim();
let version = semver;
const builtAt = process.env.SOURCE_DATE_EPOCH
  ? new Date(Number(process.env.SOURCE_DATE_EPOCH) * 1000).toISOString()
  : "not recorded (content-addressed)";

function contentHash(dir, templates) {
  const hash = createHash("sha256");
  const walk = (d) =>
    readdirSync(d, { withFileTypes: true })
      .sort((a, b) => (a.name < b.name ? -1 : 1))
      .flatMap((e) => (e.isDirectory() ? walk(resolve(d, e.name)) : [resolve(d, e.name)]));
  for (const file of [...walk(dir), ...templates]) {
    hash.update(file.slice(uiDir.length));
    hash.update(readFileSync(file));
  }
  return hash.digest("hex").slice(0, 10);
}

// ── Themes (station first — it is the :root fallback, like the generator) ──

const themeNames = [
  ...readdirSync(themesDir)
    .filter((f) => f.endsWith(".json"))
    .map((f) => basename(f, ".json"))
    .filter((n) => n === "station"),
  ...readdirSync(themesDir)
    .filter((f) => f.endsWith(".json"))
    .map((f) => basename(f, ".json"))
    .filter((n) => n !== "station")
    .sort(),
];
const DEFAULT_THEME = "starfield";
const titleCase = (s) => s.charAt(0).toUpperCase() + s.slice(1);

// ── Build ─────────────────────────────────────────────────────────────────

// Refresh the generated tokens so the kit can never ship stale ones.
execFileSync(process.execPath, ["scripts/generate-tokens.mjs"], { cwd: uiDir, stdio: "inherit" });
if (!existsSync(generatedCss)) {
  console.error(`✗ Missing ${generatedCss} — tokens generation failed`);
  process.exit(1);
}

rmSync(outDir, { recursive: true, force: true });
mkdirSync(outDir, { recursive: true });

cpSync(generatedCss, resolve(outDir, "tokens.css"));
cpSync(resolve(kitSrcDir, "src/base.css"), resolve(outDir, "base.css"));

// Only the fonts base.css actually references travel with the kit.
const baseCss = readFileSync(resolve(outDir, "base.css"), "utf-8");
const fontFiles = [...new Set([...baseCss.matchAll(/url\(fonts\/([^)]+)\)/g)].map((m) => m[1]))];
if (fontFiles.length === 0) {
  console.error("✗ base.css references no fonts/ — refusing to build an empty font set");
  process.exit(1);
}
mkdirSync(resolve(outDir, "fonts"), { recursive: true });
for (const file of fontFiles) {
  const src = resolve(fontsDir, file);
  if (!existsSync(src)) {
    console.error(`✗ base.css loads fonts/${file} but it is not in public/assets/fonts/`);
    process.exit(1);
  }
  cpSync(src, resolve(outDir, "fonts", file));
}

// The icon library's sprite travels with the kit (hand-drawn source in
// design/assets/icons; never regenerated here).
cpSync(resolve(repoRoot, "design/assets/icons/sprite.svg"), resolve(outDir, "icons.svg"));

// Everything shipped so far + the templates below decide the version.
version = `${semver}+${contentHash(outDir, [
  resolve(kitSrcDir, "README.md"),
  resolve(kitSrcDir, "preview.html"),
  resolve(kitSrcDir, "VERSION"),
])}`;

// kit.json
const kitJson = {
  name: "worlds-kit",
  version,
  built_at: builtAt,
  source: "personal-world",
  default_theme: DEFAULT_THEME,
  themes: themeNames,
};
writeFileSync(resolve(outDir, "kit.json"), JSON.stringify(kitJson, null, 2) + "\n", "utf-8");

// README.md
const themeList = themeNames
  .map((n) => (n === DEFAULT_THEME ? `- \`${n}\` — Worlds product default` : `- \`${n}\``))
  .join("\n");
const readmeTemplate = readFileSync(resolve(kitSrcDir, "README.md"), "utf-8");
const readme = readmeTemplate
  .replaceAll("{{VERSION}}", version)
  .replaceAll("{{BUILT_AT}}", builtAt)
  .replaceAll("{{THEME_LIST}}", themeList);
writeFileSync(resolve(outDir, "README.md"), readme, "utf-8");

// preview.html
const themeOptions = themeNames
  .map(
    (n) =>
      `            <option value="${n}"${n === DEFAULT_THEME ? " selected" : ""}>${titleCase(n)}</option>`,
  )
  .join("\n");
const previewTemplate = readFileSync(resolve(kitSrcDir, "preview.html"), "utf-8");
const preview = previewTemplate
  .replaceAll("{{VERSION}}", version)
  .replaceAll("{{BUILT_AT}}", builtAt)
  .replaceAll("{{THEME_OPTIONS}}", themeOptions);
writeFileSync(resolve(outDir, "preview.html"), preview, "utf-8");

console.log(`✓ Built Worlds kit → ${outDir}`);
console.log(`  version:       ${version}`);
console.log(`  built_at:      ${builtAt}`);
console.log(`  default_theme: ${DEFAULT_THEME}`);
console.log(`  themes:        ${themeNames.join(", ")}`);
console.log(`  fonts:         ${fontFiles.join(", ")}`);
console.log(`  icons:         icons.svg (the Worlds icon library sprite)`);