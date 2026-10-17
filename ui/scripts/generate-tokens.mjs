#!/usr/bin/env node

/**
 * generate-tokens.mjs
 *
 * Generates CSS custom properties and TypeScript types from design tokens.
 *
 * Sources:
 *   - ../design/tokens.json   — token NAMES and immutable values
 *     (targets/, focus/, motion/ categories carry `_value` and are
 *     contract-immutable: never overridden by themes or density).
 *   - ../design/themes/*.json — per-theme values. Station is the `:root`
 *     fallback (NOT the product default — that is DEFAULT_THEME in
 *     src/app/prefs-dom.ts, starfield) and is emitted on `:root` FIRST so every [data-theme] block,
 *     having equal specificity and later position, overrides it.
 *
 * Usage:
 *   node scripts/generate-tokens.mjs           # all themes
 */

import { readFileSync, writeFileSync, readdirSync } from "fs";
import { dirname, resolve, basename } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const themesDir = resolve(__dirname, "../../design/themes");
const designTokensPath = resolve(__dirname, "../../design/tokens.json");
const cssOutput = resolve(__dirname, "../src/generated/tokens.css");
const tsOutput = resolve(__dirname, "../src/generated/tokens.ts");

const allThemeFiles = readdirSync(themesDir).filter((f) => f.endsWith(".json"));

/** Station (the :root fallback) must come first; rest keeps sorted order. */
const themeFiles = [
  ...allThemeFiles.filter((f) => basename(f, ".json") === "station"),
  ...allThemeFiles.filter((f) => basename(f, ".json") !== "station").sort(),
];

// ─── Immutable contract tokens (design/tokens.json) ───────────────────────

/**
 * Walk the given categories of design/tokens.json and collect every leaf
 * that carries a string `_value`. These are accessibility-contract
 * constants (44px targets, focus ring structure, motion default) — they
 * live on :root and are never redefined by any theme block.
 */
function readImmutableTokens(categories) {
  const design = JSON.parse(readFileSync(designTokensPath, "utf-8"));
  const out = [];
  for (const category of categories) {
    const values = design[category];
    if (!values || typeof values !== "object" || Array.isArray(values)) continue;
    for (const [prop, val] of Object.entries(values)) {
      if (prop.startsWith("_")) continue;
      if (typeof val !== "object" || val === null) continue;
      if (typeof val._value !== "string") continue;
      out.push({
        cssVar: `--pw-${category}-${prop.replace(/\./g, "-")}`,
        value: val._value,
        category,
        prop,
      });
    }
  }
  return out;
}

const immutableTokens = readImmutableTokens(["targets", "focus", "motion"]);

// ─── CSS Generation ───────────────────────────────────────────────────────

let css = `/**
 * PROJECT WORLDS — Generated Design Tokens
 *
 * ⚠️  THIS FILE IS GENERATED. Do not edit by hand.
 * Source: design/tokens.json (immutable) + design/themes/*.json
 * Generator: scripts/generate-tokens.mjs
 *
 * Cascade order matters: immutable :root block first, then the station
 * default on :root, then one [data-theme="<name>"] block per other theme.
 * :root and [data-theme="…"] have equal specificity, so the later block
 * wins — which is exactly how a theme override must behave.
 *
 * Run: node scripts/generate-tokens.mjs
 */\n\n`;

css += `  /* Accessibility-contract constants — immutable, never themed over. */\n`;
css += `:root {\n`;
for (const t of immutableTokens) {
  css += `  ${t.cssVar}: ${t.value};\n`;
}
css += `}\n`;

for (const file of themeFiles) {
  const themeName = basename(file, ".json");
  const data = JSON.parse(readFileSync(resolve(themesDir, file), "utf-8"));

  if (themeName === "station") {
    css += `\n/* :root fallback theme: station (first-run default is DEFAULT_THEME). Also\n   addressable as [data-theme="station"] so an element (a theme swatch) can show\n   Station's own colours inside another theme. */\n:root, [data-theme="station"] {\n`;
  } else {
    css += `\n[data-theme="${themeName}"] {\n`;
  }

  for (const [category, values] of Object.entries(data)) {
    if (category === "_comment" || category === "_author" || category.startsWith("_")) continue;
    if (typeof values !== "object" || Array.isArray(values)) continue;

    // Add category comment
    const comment = values._comment || "";
    if (comment) {
      css += `  /* ${comment.substring(0, 80)} */\n`;
    }

    for (const [prop, val] of Object.entries(values)) {
      if (prop === "_comment" || prop.startsWith("_")) continue;
      if (typeof val !== "string") continue;

      const cssVar = `--pw-${category}-${prop.replace(/\./g, "-")}`;
      css += `  ${cssVar}: ${val};\n`;
    }
    css += `\n`;
  }

  css += `}\n`;
}

writeFileSync(cssOutput, css, "utf-8");
console.log(`✓ Generated ${cssOutput}`);
console.log(`  Themes: ${themeFiles.map((f) => basename(f, ".json")).join(", ")}`);
console.log(`  Immutable tokens: ${immutableTokens.map((t) => t.cssVar).join(", ")}`);

// ─── TypeScript Generation ────────────────────────────────────────────────

// Build a union of all token paths from the station theme (base)
const stationData = JSON.parse(
  readFileSync(resolve(themesDir, "station.json"), "utf-8"),
);

const tokenEntries = immutableTokens.map((t) => ({
  cssVar: t.cssVar,
  category: t.category,
  prop: t.prop,
}));

for (const [category, values] of Object.entries(stationData)) {
  if (category === "_comment" || category.startsWith("_")) continue;
  if (typeof values !== "object" || Array.isArray(values)) continue;

  for (const [prop, val] of Object.entries(values)) {
    if (prop === "_comment" || prop.startsWith("_")) continue;
    // Same filter the CSS generator uses: only string leaves become
    // custom properties. Without this, nested groups (e.g. density)
    // produced fake tokens like --pw-density-comfortable.
    if (typeof val !== "string") continue;
    const cssVar = `--pw-${category}-${prop.replace(/\./g, "-")}`;
    tokenEntries.push({ cssVar, category, prop });
  }
}

const themeNames = themeFiles.map((f) => basename(f, ".json"));

const ts = `/**
 * PROJECT WORLDS — Generated Design Token Types
 *
 * ⚠️  THIS FILE IS GENERATED. Do not edit by hand.
 * Source: design/tokens.json + design/themes/station.json
 * Generator: scripts/generate-tokens.mjs
 *
 * Usage:
 *   import { TOKENS } from "./generated/tokens";
 *   element.style.color = TOKENS["--pw-text-primary"];
 */

/** All available CSS custom property names */
export type TokenName = ${tokenEntries.map((t) => `"${t.cssVar}"`).join("\n  | ")};

/** Token values keyed by CSS variable name */
export const TOKENS: Record<TokenName, string> = {
${tokenEntries.map((t) => `  "${t.cssVar}": "var(${t.cssVar})"`).join(",\n")}
} as const;

/** Get a token value as a CSS string */
export function token(name: TokenName): string {
  return \`var(\${name})\`;
}

/** Theme names available (generated from design/themes/*.json) */
export type ThemeName = ${themeNames.map((n) => `"${n}"`).join(" | ")};

/** All theme selectors (station is the :root fallback) */
export const THEMES: Record<ThemeName, string> = {
${themeNames
  .map((n) => `  ${JSON.stringify(n)}: ${n === "station" ? '":root"' : `'[data-theme="${n}"]'`}`)
  .join(",\n")},
} as const;
`;

writeFileSync(tsOutput, ts, "utf-8");
console.log(`✓ Generated ${tsOutput}`);
console.log(`  Token entries: ${tokenEntries.length}`);
