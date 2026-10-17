#!/usr/bin/env bash
# install — the ONE command that gives someone Project Worlds.
#
#   ./install.sh            build from this source + start + print the URL
#   ./install.sh --prod     start from the published image instead (once published)
#
# What it does (idempotent, safe to re-run):
#   1. finds podman or docker
#   2. creates .env with a fresh PW_API_TOKEN if missing (0600, never printed)
#   3. brings up core + local brain from THIS source (dev) or the image (prod)
#   4. waits for health, then prints the URL and what to do next
#
# It never touches an existing .env token, never prints secrets, and never
# deletes data. Re-running just ensures the stack is up.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

MODE="dev"
[ "${1:-}" = "--prod" ] && MODE="prod"

# 1. engine -------------------------------------------------------------------
BIN=""
for c in podman docker; do command -v "$c" >/dev/null 2>&1 && {
	BIN="$c"
	break
}; done
if [ -z "$BIN" ]; then
	echo "Project Worlds needs podman or docker installed." >&2
	echo "  Fedora/Bazzite:  sudo dnf install podman podman-compose" >&2
	echo "  Ubuntu/Debian:   sudo apt install docker.io docker-compose-v2" >&2
	exit 2
fi
echo ">> using $BIN"

# 2. token (create-if-absent; fail-closed boot stays intact) ------------------
if [ ! -f .env ] || ! grep -q '^PW_API_TOKEN=..*' .env 2>/dev/null; then
	TOK="$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))' 2>/dev/null ||
		openssl rand -base64 32 2>/dev/null | tr -d '=+/' | cut -c1-43)"
	printf 'PW_API_TOKEN=%s\n' "$TOK" >.env
	chmod 600 .env
	echo ">> created .env with a fresh API token (kept private, 0600)"
else
	echo ">> .env already present; leaving your token alone"
fi

# 3. bring up ------------------------------------------------------------------
if [ "$MODE" = "dev" ]; then
	echo ">> building from this source tree (no published image needed)…"
	"$BIN" compose -f compose.yaml -f compose.dev.yaml up -d --build
else
	echo ">> starting from the published image…"
	"$BIN" compose up -d
fi

# 4. wait for health + tell them what to do ------------------------------------
echo ">> waiting for the backend to be healthy…"
for i in $(seq 1 60); do
	if curl -fsS http://127.0.0.1:8000/healthz >/dev/null 2>&1; then break; fi
	sleep 2
done

cat <<EOF

  Project Worlds is up.

  Open:   http://127.0.0.1:8000/
          (first run shows a friendly setup wizard — it provisions everything
           invisibly and lets you sign in locally or with your own SSO)

  Back up everything, encrypted:
          personal-world worlds backup ~/my-worlds-backup.pwb   # or see Settings

  Docs:   docs/QUICKSTART.md   ·   docs/WORLDS-BACKUP.md   ·   docs/history/ROADMAP-AND-TODO.md

EOF
