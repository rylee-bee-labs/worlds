#!/usr/bin/env bash
#
# scripts/build-app.sh — build the Project Worlds interface and stage it
# into the backend's serve directory.
#
# Reads:    ui/            (the React rebuild — part of this repo since
#                           the 2026-09-22 trunk merge)
# Writes:   src/personal_world/static/app/   (gitignored build output)
#
# The container image does NOT need this script: its ui-build stage runs
# the same npm commands internally. This script exists for source
# checkouts that run uvicorn directly (development, bare-metal deploys).
#
# Why we don't commit the artifacts: the build is deterministic from
# ui/ + the lockfile; committing it would bloat the repo and require a
# commit on every rebuild. This script is the interface (pun intended).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UI="$REPO_ROOT/ui"
DEST="$REPO_ROOT/src/personal_world/static/app"

if [ ! -f "$UI/package.json" ]; then
    echo "✗ ui/ not found at $UI" >&2
    exit 1
fi

echo ">> building ui/ (npm ci + npm run build)"
cd "$UI"
[ -d node_modules ] || npm ci --no-audit --no-fund
npm run build

if [ ! -f "$UI/dist/index.html" ]; then
    echo "✗ build looks incomplete: missing $UI/dist/index.html" >&2
    exit 1
fi

echo ">> staging dist/ -> src/personal_world/static/app/"
mkdir -p "$DEST"
rm -rf "$DEST"
mkdir -p "$DEST"
cp -r "$UI/dist/." "$DEST/"

echo "✓ interface staged at $DEST"
echo "  (restart the app; / serves it)"
