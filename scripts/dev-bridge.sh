#!/usr/bin/env bash
# Dev preview of the Bridge against real local sources. Loopback only;
# never touches a live instance. Usage:
#   PW_PH_CLI=/path/to/project-home/bin/project PW_LAB_CLI=/path/to/lab \
#     scripts/dev-bridge.sh [data-dir]
# Then open http://127.0.0.1:4180/ . Stop with Ctrl-C.
# PW_PH_CLI / PW_LAB_CLI are optional: unset sources show honest
# "not set up yet" states. PW_DEV_AUTH_BYPASS only works on loopback.
set -euo pipefail
cd "$(dirname "$0")/.."
DATA_DIR="${1:-${TMPDIR:-/tmp}/pw-bridge-dev}"
mkdir -p "$DATA_DIR/data"
[ -d "$DATA_DIR/config" ] || cp -r config "$DATA_DIR/config"
export PW_DEV_AUTH_BYPASS=1
export PW_API_TOKEN="dev-$(head -c12 /dev/urandom | od -An -tx1 | tr -d ' \n')"
export PW_DATA_DIR="$DATA_DIR/data" PW_CONFIG_DIR="$DATA_DIR/config"
uv run uvicorn personal_world.worlds.production:app_from_env --factory --app-dir src \
  --host 127.0.0.1 --port "${PW_DEV_API_PORT:-8010}" &
API_PID=$!
trap 'kill $API_PID 2>/dev/null' EXIT
(cd ui && npm run -s build && VITE_API_PROXY_TARGET="http://127.0.0.1:${PW_DEV_API_PORT:-8010}" \
  npx vite preview --host 127.0.0.1 --port "${PW_DEV_UI_PORT:-4180}" --strictPort)
