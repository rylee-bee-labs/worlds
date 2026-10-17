#!/bin/sh
# safe-commit.sh -- stage explicit paths, run pytest, commit.
# Guards against the shared-checkout hazard: `git add -A` sweeping a
# colleague's WIP. Usage:
#   scripts/safe-commit.sh -m "message" <path> [<path> ...]
#   scripts/safe-commit.sh --force -m "message" <path> ...
#   PW_SAFE_COMMIT_SKIP_TESTS=1 scripts/safe-commit.sh ...   (docs-only lanes)
#
# Exit codes: 0 committed; 1 guard refused or tests failed; 2 usage.
set -eu

force=0
while [ $# -gt 0 ]; do
    case "$1" in
        --force) force=1; shift ;;
        -m) msg=$2; shift 2 ;;
        -m*) msg=${1#-m}; shift ;;
        --) shift; break ;;
        -*) printf 'unknown flag: %s\n' "$1" >&2; exit 2 ;;
        *) break ;;
    esac
done
[ $# -ge 1 ] || { printf 'usage: safe-commit.sh -m "message" <path> ...\n' >&2; exit 2; }
[ -n "${msg:-}" ] || { printf 'error: -m "message" required\n' >&2; exit 2; }

for p in "$@"; do
    [ -e "$p" ] || { printf 'error: path not found: %s\n' "$p" >&2; exit 2; }
done

# Files dirty in the working tree that are NOT among the given paths.
# Note the `|| :` — under `set -e`, a final `[ ... ] && cmd` that
# evaluates false would otherwise abort the whole script (exit 1, no
# message) whenever the *last* dirty file is one we were asked to commit,
# i.e. exactly in the clean, bounded case this script exists to serve.
# Untracked directories stay collapsed (one entry, e.g. `frontend-v2/`),
# so a big untracked prototype tree counts as one outside item, not
# hundreds. A collapsed directory entry is "ours" when a named path lives
# beneath it (`docs/p1/` vs `docs/p1/SPEC.md`).
outside=$(git status --porcelain --untracked-files=normal | cut -c4- \
    | while IFS= read -r f; do
        skip=0
        for p in "$@"; do
            case "$f" in "$p"|"$p"/*) skip=1; break ;; esac
            case "$f" in */) case "$p" in "$f"*) skip=1; break ;; esac ;; esac
        done
        if [ "$skip" -eq 0 ]; then printf '%s\n' "$f"; fi
    done || :)
out_count=$(printf '%s\n' "$outside" | grep -c . || :)
if [ "$out_count" -gt 5 ] && [ "$force" -eq 0 ]; then
    printf 'error: %s modified files outside the given paths:\n' "$out_count" >&2
    printf '%s\n' "$outside" >&2
    printf 're-run with --force if this is intentional.\n' >&2
    exit 1
fi

if [ "${PW_SAFE_COMMIT_SKIP_TESTS:-0}" != "1" ]; then
    if ! uv run pytest -q -p no:cacheprovider; then
        printf 'error: pytest failed; nothing staged or committed.\n' >&2
        exit 1
    fi
fi

git add -- "$@"
git commit -m "$msg"
printf 'committed %s path(s).\n' "$#"
