#!/usr/bin/env bash
# dev — the one obvious way to run Project Worlds from the CURRENT checkout.
#
#   scripts/dev.sh up        build from current source + start (the newest build)
#   scripts/dev.sh newest    force-recreate from current source (fresh containers)
#   scripts/dev.sh wipe      remove dev containers + the dev image (next `up`
#                            rebuilds from newest source). NEVER touches the
#                            world-data / ollama-data volumes, config/, or source.
#   scripts/dev.sh status    what is running + which image owns :8000
#   scripts/dev.sh logs      follow core logs
#
# Play-nice rules baked in:
#   * Always builds from THIS checkout (compose.dev.yaml sets pull_policy: never,
#     so a stale GHCR `latest` can never silently win).
#   * wipe is loud and scoped: containers + dev image only. Your data survives.
#   * PW_DEV_AUTH_BYPASS is opt-in (set it in your shell to enable the
#     true-loopback bypass); the dev/mirror default is OFF so it matches prod.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

COMPOSE_BIN=""
for c in podman docker; do command -v "$c" >/dev/null 2>&1 && {
	COMPOSE_BIN="$c"
	break
}; done
[ -n "$COMPOSE_BIN" ] || {
	echo "need podman or docker on PATH" >&2
	exit 2
}

COMPOSE=("$COMPOSE_BIN" compose -f compose.yaml -f compose.dev.yaml)
DEV_IMAGE="personal-world:dev"

case "${1:-up}" in
up)
	echo ">> building from current source and starting…"
	"${COMPOSE[@]}" up -d --build
	echo ">> Project Worlds:  http://127.0.0.1:${PW_PORT:-8000}/station/"
	;;
newest)
	echo ">> recreating containers from current source…"
	"${COMPOSE[@]}" up -d --build --force-recreate
	echo ">> Project Worlds:  http://127.0.0.1:${PW_PORT:-8000}/station/"
	;;
wipe)
	echo ">> stopping + removing dev containers (data volumes are NOT touched)…"
	"${COMPOSE[@]}" down --remove-orphans || true
	if "$COMPOSE_BIN" image exists "$DEV_IMAGE" >/dev/null 2>&1; then
		echo ">> removing dev image $DEV_IMAGE (next up rebuilds from newest source)…"
		"$COMPOSE_BIN" rmi "$DEV_IMAGE" >/dev/null 2>&1 || true
	fi
	echo ">> wiped. world-data / ollama-data / config / source untouched."
	echo ">> run:  scripts/dev.sh up"
	;;
status)
	"$COMPOSE_BIN" ps -a --format "table {{.Names}}\t{{.Image}}\t{{.Status}}" 2>/dev/null |
		grep -Ei "names|personal-world|ollama" || true
	echo
	if [ "$COMPOSE_BIN" = podman ]; then
		"$COMPOSE_BIN" inspect personal-world-core-1 --format 'core image = {{.Config.Image}}' 2>/dev/null ||
			echo "core container not running"
	fi
	;;
logs)
	"${COMPOSE[@]}" logs -f --tail=100 core
	;;
*)
	grep '^#   scripts/dev.sh' "$0" | sed 's/^#   //'
	exit 2
	;;
esac
