#!/usr/bin/env node

/**
 * generate-api-types.mjs
 *
 * Generates TypeScript types from the Project Worlds OpenAPI spec.
 * Uses the local spec (src/generated/openapi.json) as source of truth.
 * The spec is hand-maintained from the server source — the deployed
 * Station disables /openapi.json (HTTP 500). See README → "Updating
 * the API Spec".
 *
 * Usage: node scripts/generate-api-types.mjs
 */

import { spawnSync } from "child_process";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";
import { existsSync } from "fs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const specPath = resolve(__dirname, "../src/generated/openapi.json");
const outputPath = resolve(__dirname, "../src/generated/api-types.ts");

if (!existsSync(specPath)) {
  console.error(`❌ OpenAPI spec not found at ${specPath}`);
  process.exit(1);
}

console.log(`Generating types from ${specPath}...`);

// openapi-typescript needs the TypeScript *JS* compiler API, which
// TypeScript 7 (native) no longer ships. Run it in isolation with its own
// pinned TypeScript 5 so the app itself can stay on TypeScript 7.
// Pinned exactly for reproducible output.
const CODEGEN_OPENAPI = "openapi-typescript@7.13.0";
const CODEGEN_TS = "typescript@5.9.3";

const result = spawnSync(
  "npm",
  [
    "exec",
    "--yes",
    `--package=${CODEGEN_OPENAPI}`,
    `--package=${CODEGEN_TS}`,
    "--",
    "openapi-typescript",
    specPath,
    "-o",
    outputPath,
  ],
  { stdio: "inherit", cwd: resolve(__dirname, "..") },
);

if (result.error || result.status !== 0) {
  console.error(
    `❌ Failed to generate types: ${result.error?.message ?? `exit ${result.status}`}`,
  );
  process.exit(1);
}
console.log(`✓ Generated ${outputPath}`);
