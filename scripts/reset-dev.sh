#!/usr/bin/env bash
# reset-dev — wipe a DEVELOPMENT instance back to first-run, safely.
#
# Project Worlds is universal + local-first. During development we want
# ephemeral sessions: wipe everything the app generated and get a clean
# first-run (setup wizard) again. This script is deliberately loud and
# default-dry-run so it can never surprise anyone.
#
# SAFETY RULES (do not weaken):
#   * Default is DRY-RUN. Nothing is removed unless you pass --yes-i-wipe.
#   * Only touches UNTRACKED generated state: the local data/ directory or a
#     named Docker volume. Never touches git-tracked files, the repo, or code.
#   * Refuses to run against a path/volume that looks like it holds a
#     production instance unless you also pass --i-know-this-is-prod.
#   * Prints exactly what it will remove before removing it.
#
# USAGE
#   scripts/reset-dev.sh                      # dry-run: show what would go
#   scripts/reset-dev.sh --yes-i-wipe         # wipe local ./data (dev)
#   scripts/reset-dev.sh --volume pw_data --yes-i-wipe
#                                             # wipe a compose volume instead
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${PW_DATA_DIR:-$REPO_ROOT/data}"
VOLUME=""
CONFIRM=0
PROD_OK=0

while [[ $# -gt 0 ]]; do
	case "$1" in
	--yes-i-wipe)
		CONFIRM=1
		shift
		;;
	--i-know-this-is-prod)
		PROD_OK=1
		shift
		;;
	--volume)
		VOLUME="${2:-}"
		shift 2
		;;
	-h | --help)
		grep '^#' "$0" | sed 's/^# \{0,1\}//'
		exit 0
		;;
	*)
		echo "unknown flag: $1" >&2
		exit 2
		;;
	esac
done

echo "Project Worlds — dev reset"
echo "repo:      $REPO_ROOT"
if [[ -n "$VOLUME" ]]; then
	echo "target:    docker volume '$VOLUME'"
else
	echo "target:    $DATA_DIR"
fi
echo

# --- guard: production-looking instance -------------------------------------
is_prod_looking() {
	# Heuristic: a production instance is one the operator has explicitly
	# marked, or a volume not prefixed for dev. We stay conservative.
	if [[ -n "$VOLUME" && "$VOLUME" != *dev* && "$VOLUME" != *pw_* ]]; then return 0; fi
	if [[ -f "$DATA_DIR/.prod" ]]; then return 0; fi
	return 1
}
if is_prod_looking && [[ "$PROD_OK" -ne 1 ]]; then
	echo "REFUSED: target looks like a production instance."
	echo "If you truly intend this, re-run with --i-know-this-is-prod."
	exit 3
fi

# --- enumerate what would be removed (dry-run by default) -------------------
list_targets() {
	if [[ -n "$VOLUME" ]]; then
		docker volume inspect "$VOLUME" >/dev/null 2>&1 &&
			echo "docker volume: $VOLUME" ||
			echo "docker volume: $VOLUME (does not exist)"
	else
		if [[ -d "$DATA_DIR" ]]; then
			echo "directory: $DATA_DIR (contents:"
			ls -A "$DATA_DIR" | sed 's/^/    /'
			echo ")"
		else
			echo "directory: $DATA_DIR (does not exist)"
		fi
	fi
}

echo "Would remove:"
list_targets
echo

if [[ "$CONFIRM" -ne 1 ]]; then
	echo "DRY-RUN: nothing was removed."
	echo "To actually wipe, re-run with:  --yes-i-wipe"
	exit 0
fi

# --- actually wipe -----------------------------------------------------------
if [[ -n "$VOLUME" ]]; then
	echo "Removing docker volume '$VOLUME'..."
	docker volume rm "$VOLUME"
else
	echo "Removing $DATA_DIR..."
	rm -rf "$DATA_DIR"
fi

echo
echo "Done. Next start is a clean first-run: the setup wizard will appear."
echo "Your git history and repo are untouched; restore any committed state with git."
