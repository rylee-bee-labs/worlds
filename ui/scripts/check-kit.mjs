#!/usr/bin/env node

/**
 * check-kit.mjs — the `kit:check` gate.
 *
 * Rebuilds the Worlds kit and fails when the result no longer matches what is
 * committed under ui/dist-kit/ (the same idea as `tokens:check`, but covering
 * untracked additions too — a stale file that someone adds is drift, not a
 * clean tree).
 *
 * When dist-kit is not committed yet, "differs from committed" has no
 * baseline, so it verifies the next-best thing it can prove: the build is
 * deterministic and idempotent (a second build is byte-identical).
 *
 * Usage: node scripts/check-kit.mjs
 */

import { execFileSync, spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const uiDir = resolve(__dirname, "..");
const repoRoot = resolve(uiDir, "..");
const outDir = resolve(uiDir, "dist-kit");
const gitPath = "ui/dist-kit";

function runBuild() {
  const result = spawnSync(process.execPath, [resolve(__dirname, "build-kit.mjs")], {
    cwd: uiDir,
    stdio: "inherit",
  });
  if (result.status !== 0) process.exit(result.status ?? 1);
}

/** relpath → sha256 for every file under dir (sorted, so it is stable). */
function hashTree(dir) {
  const out = new Map();
  if (!existsSync(dir)) return out;
  const walk = (current) => {
    for (const entry of readdirSync(current).sort()) {
      const full = join(current, entry);
      if (statSync(full).isDirectory()) walk(full);
      else out.set(relative(dir, full), createHash("sha256").update(readFileSync(full)).digest("hex"));
    }
  };
  walk(dir);
  return out;
}

function diffTrees(before, after) {
  const problems = [];
  for (const [path, hash] of after) {
    if (!before.has(path)) problems.push(`added:    ${path}`);
    else if (before.get(path) !== hash) problems.push(`changed:  ${path}`);
  }
  for (const path of before.keys()) {
    if (!after.has(path)) problems.push(`removed:  ${path}`);
  }
  return problems;
}

// Start from a guaranteed-fresh build.
runBuild();

const tracked = (() => {
  try {
    return execFileSync("git", ["ls-files", "--", gitPath], { cwd: repoRoot, encoding: "utf-8" }).trim();
  } catch {
    return "";
  }
})();

if (tracked) {
  // Committed dist-kit → compare the working tree against HEAD.
  try {
    execFileSync("git", ["diff", "--exit-code", "--", gitPath], { cwd: repoRoot, stdio: "inherit" });
  } catch {
    console.error("\n✗ dist-kit differs from the committed kit. Run `npm run kit:build` and commit dist-kit.");
    process.exit(1);
  }
  const untracked = execFileSync("git", ["ls-files", "--others", "--exclude-standard", "--", gitPath], {
    cwd: repoRoot,
    encoding: "utf-8",
  }).trim();
  if (untracked) {
    console.error(`\n✗ dist-kit has untracked files:\n${untracked}`);
    process.exit(1);
  }
  console.log("✓ dist-kit matches the committed kit");
} else {
  // Not committed yet — prove the build is deterministic and idempotent.
  const before = hashTree(outDir);
  runBuild();
  const after = hashTree(outDir);
  const problems = diffTrees(before, after);
  if (problems.length > 0) {
    console.error(`\n✗ kit build is not reproducible — a rebuild changed dist-kit:\n${problems.join("\n")}`);
    process.exit(1);
  }
  console.log("✓ dist-kit is not committed yet; verified the build is deterministic and idempotent");
  console.log(`  (${after.size} files) — commit dist-kit to enable the differs-from-committed gate`);
}