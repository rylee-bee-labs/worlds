#!/usr/bin/env node

/**
 * stamp-kit.mjs <target-dir>
 *
 * Copies the built Worlds kit (ui/dist-kit/) into a consuming project's
 * vendor directory and leaves a STAMP recording exactly which build it is.
 *
 *   node scripts/stamp-kit.mjs vendor/worlds-kit
 *
 * The STAMP is derived entirely from the build (version + built_at), so
 * re-stamping the same kit is a no-op in content terms — idempotent. A target
 * that already holds a STAMP is mirrored (replaced wholesale); one that does
 * not is refused unless --force is passed, so a mistyped path can't eat a
 * directory of someone else's work.
 *
 * Usage:
 *   node scripts/stamp-kit.mjs <target-dir> [--force]
 */

import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { basename, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const uiDir = resolve(__dirname, "..");
const distKit = resolve(uiDir, "dist-kit");

const args = process.argv.slice(2);
const force = args.includes("--force");
const targetArg = args.find((a) => !a.startsWith("--"));

if (!targetArg) {
  console.error("usage: node scripts/stamp-kit.mjs <target-dir> [--force]");
  process.exit(2);
}
const target = resolve(process.cwd(), targetArg);

if (!existsSync(resolve(distKit, "kit.json"))) {
  console.error(`✗ ${distKit} has no kit.json — run \`npm run kit:build\` first`);
  process.exit(1);
}
const kit = JSON.parse(readFileSync(resolve(distKit, "kit.json"), "utf-8"));

if (existsSync(target)) {
  const entries = readdirSync(target);
  const stamped = entries.includes("STAMP");
  if (entries.length > 0 && !stamped && !force) {
    console.error(
      `✗ ${target} is not empty and has no STAMP — refusing to overwrite.\n` +
        `  Pass --force if that is really the target.`,
    );
    process.exit(1);
  }
  rmSync(target, { recursive: true, force: true });
}

mkdirSync(target, { recursive: true });
cpSync(distKit, target, { recursive: true });

const stamp = [
  `name: worlds-kit`,
  `version: ${kit.version}`,
  `date: ${kit.built_at}`,
  `source: ${kit.source}`,
  `note: do not hand-edit; run stamp-kit`,
  "",
].join("\n");
writeFileSync(resolve(target, "STAMP"), stamp, "utf-8");

console.log(`✓ Stamped worlds-kit ${kit.version} → ${target}`);
console.log(`  (files mirrored from ${basename(distKit)}/; see ${basename(target)}/STAMP)`);