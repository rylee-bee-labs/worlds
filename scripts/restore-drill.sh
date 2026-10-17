#!/usr/bin/env bash
# restore-drill — a REAL, timed Memory backup→restore drill for Project Worlds.
#
# Rebuild/front-door version. The old drill proved the encrypted
# `worlds_backup` bundle of the deleted `personal_world.api:create_app`
# instance (world.json, journal.ndjson, users.json, vault.enc, ...). That
# whole path is gone: the production app is
# `personal_world.worlds.production:create_app`, durable state is the
# Memory store in `$PW_DATA_DIR/worlds.db`, and backup/restore are the real
# route `POST /api/memory/backup` and the real function
# `personal_world.worlds.memory_store.restore_backup`.
#
# Proves, with wall-clock evidence, that Memory rows written to one
# instance survive a backup and come back through the API in a FRESH data
# dir:
#   seed (real API) → backup (real route) → refusals → restore
#   (restore_backup into empty B) → boot the app on B → same rows via API.
#
# Phases (each timed):
#   1. seed      temp instance A: production app on 127.0.0.1 with a
#                bootstrap owner policy, sign in, write kept/later/records
#                rows through POST /api/memory/{table}; snapshot A via
#                authenticated reads.
#   2. backup    POST /api/memory/backup → a private copy in A's backups/.
#   3. refusals  restore_backup must refuse: a corrupted file, a
#                non-Worlds sqlite file, and a non-empty target. A refused
#                restore writes nothing; it never overwrites.
#   4. restore   fresh data dir B; restore_backup copies the rows and
#                rebuilds the find index; B's worlds.db is 0600.
#   5. verify    boot the production app on B (its own config, its own
#                bootstrap session) and read the same rows back through
#                the API: kept, later, records and history (A's rows plus
#                the one appended `restored` event).
#   6. teardown  kill any server this drill started (PID from pgrep,
#                cmdline verified before kill), remove temp dirs.
#
# FLAGS
#   --report DIR      copy the run's evidence (timings, JSON snapshots) to DIR
#   --keep            keep the temp workspace for debugging
#   --port N          preferred loopback port (default 8022)
#   --corrupt-backup  failure-path drill: corrupt the backup and prove that
#                     restore_backup refuses it (prints PASS on refusal)
#
# SAFETY / hygiene:
#   * Binds 127.0.0.1 only; never 0.0.0.0. Every root is a temp dir: the
#     real ~/.config/personal-world is never touched.
#   * The bootstrap secret is generated at runtime, lives only in a 0700
#     temp file / the server env, and is never printed or passed in argv.
#     The session id and CSRF token travel to curl in a 0600 config file.
#   * Read-only against the repo: writes go to temp dirs only.
#
# USAGE
#   scripts/restore-drill.sh
#   scripts/restore-drill.sh --report DIR
#   scripts/restore-drill.sh --keep
#   scripts/restore-drill.sh --port 8022
#   scripts/restore-drill.sh --corrupt-backup
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREFERRED_PORT=8022
REPORT_DIR=""
KEEP=0
CORRUPT_BACKUP=0

while [[ $# -gt 0 ]]; do
	case "$1" in
	--report) REPORT_DIR="$2"; shift 2 ;;
	--keep) KEEP=1; shift ;;
	--port) PREFERRED_PORT="$2"; shift 2 ;;
	--corrupt-backup) CORRUPT_BACKUP=1; shift ;;
	-h | --help) awk 'NR>1{ if ($0 ~ /^set -euo/) exit; print }' "$0"; exit 0 ;;
	*) echo "unknown option: $1" >&2; exit 2 ;;
	esac
done

say() { printf '%s\n' "$*"; }
head_phase() {
	printf '\n── %s ' "$1"
	printf '─%.0s' $(seq 1 $((56 - ${#1} > 4 ? 56 - ${#1} : 4)))
	printf '\n'
}
warn() { printf 'WARN: %s\n' "$*" >&2; }
fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

now_ms() { date +%s%3N; }
DRILL_T0=$(now_ms)
PHASE_T=0
PHASE_NAME=""
TIMINGS_FILE=""   # set once WORK exists

phase_begin() { PHASE_NAME="$1"; PHASE_T=$(now_ms); }
phase_end() {
	local end; end=$(now_ms)
	printf '%s\t%s\n' "$PHASE_NAME" "$((end - PHASE_T))" >>"$TIMINGS_FILE"
	printf '    %-22s %7d ms\n' "$PHASE_NAME" "$((end - PHASE_T))"
}

# ── preflight ─────────────────────────────────────────────────────────
preflight() {
	command -v uv >/dev/null || fail "uv not found (needed for uv sync)"
	command -v curl >/dev/null || fail "curl not found"
	command -v ss >/dev/null || fail "ss not found (port checks)"
	command -v pgrep >/dev/null || fail "pgrep not found (teardown)"
	command -v openssl >/dev/null || fail "openssl not found (runtime secret)"
	[[ -d "$REPO_ROOT/.venv" ]] || {
		say "no .venv — running: uv sync --frozen --extra test --extra crypto"
		(cd "$REPO_ROOT" && uv sync --frozen --extra test --extra crypto >/dev/null)
	}
	VENV_PY="$REPO_ROOT/.venv/bin/python"
	[[ -x "$VENV_PY" ]] || fail "no .venv/bin/python after sync"
	[[ -x "$REPO_ROOT/.venv/bin/uvicorn" ]] || fail "no .venv/bin/uvicorn after sync"
	"$VENV_PY" -c "import personal_world.worlds.production" 2>/dev/null ||
		fail "cannot import personal_world.worlds.production from the venv"
	"$VENV_PY" -c "from personal_world.worlds.memory_store import restore_backup" 2>/dev/null ||
		fail "cannot import restore_backup from the venv"
}

port_busy() { ss -ltn 2>/dev/null | grep -Eq "[:.]${1}[[:space:]]"; }

pick_port() {
	local p
	for p in "$PREFERRED_PORT" $(seq $((PREFERRED_PORT + 1)) $((PREFERRED_PORT + 10))); do
		if ! port_busy "$p"; then printf '%s' "$p"; return 0; fi
	done
	fail "no free port in ${PREFERRED_PORT}..$((PREFERRED_PORT + 10))"
}

# ── temp workspace ────────────────────────────────────────────────────
setup_work() {
	WORK=$(mktemp -d "${TMPDIR:-/tmp}/pw-restore-drill.XXXXXXXX")
	chmod 700 "$WORK"
	A_DATA=$WORK/a-data; A_CFG=$WORK/a-config
	B_DATA=$WORK/b-data; B_CFG=$WORK/b-config
	BAD=$WORK/bad
	mkdir -p "$A_DATA" "$A_CFG" "$B_DATA" "$B_CFG" "$BAD" "$WORK/out" "$WORK/body"
	chmod 700 "$WORK/out" "$WORK/body"
	TIMINGS_FILE=$WORK/timings.tsv
	: >"$TIMINGS_FILE"
	BACKUPS_DIR=$A_DATA/backups
	# Runtime bootstrap secret — never printed, never in an app argv.
	SECRET_FILE=$WORK/bootstrap-secret
	umask 077
	openssl rand -hex 32 >"$SECRET_FILE"
	BOOTSTRAP_TOKEN=$(cat "$SECRET_FILE")
	SID=""
	CSRF=""
}

cleanup() {
	local rc=$?
	trap - EXIT
	# Safety net only: phases stop their servers explicitly. Run in a
	# subshell so a stop failure here can never abort the cleanup.
	if [[ "${SERVER_RUNNING:-0}" = 1 ]]; then
		(stop_server "${PORT:-}") || true
	fi
	if [[ $KEEP -eq 1 ]]; then
		say "kept temp workspace: $WORK"
	else
		rm -rf "$WORK"
	fi
	[[ $rc -ne 0 ]] && say "drill exited with status $rc"
	exit $rc
}
trap cleanup EXIT

# Write the owner policy both instances sign in with. No secret here: the
# value lives in the server env via secret_ref.
write_owner_config() { # $1=config dir
	umask 077
	cat >"$1/owner.yaml" <<YAML
schema_version: 1
public_origin: $ORIGIN
bootstrap:
  enabled: true
  secret_ref: env:PW_BOOTSTRAP_TOKEN
YAML
	chmod 600 "$1/owner.yaml"
}

# ── server helpers ────────────────────────────────────────────────────
# Start the production app bound to loopback only. The bootstrap secret
# is passed via env (not argv).
start_server() { # $1=data dir  $2=config dir
	SERVER_DATA=$1
	SERVER_CONFIG=$2
	BASE=http://127.0.0.1:$PORT
	ORIGIN=$BASE
	SERVER_RUNNING=1
	# setsid + disown: fully detached, and no job-control "Terminated"
	# chatter when teardown kills it. pgrep still matches the argv.
	setsid env \
		PW_DATA_DIR="$1" PW_CONFIG_DIR="$2" \
		PW_BOOTSTRAP_TOKEN="$BOOTSTRAP_TOKEN" \
		"$REPO_ROOT/.venv/bin/uvicorn" personal_world.worlds.production:app_from_env --factory \
		--host 127.0.0.1 --port "$PORT" \
		>"$WORK/server-$PORT.log" 2>&1 < /dev/null &
	disown
	wait_health
}

# Stop per the harness protocol: PID from pgrep, cmdline verified,
# kill issued in its own command (never on the start line).
stop_server() {
	local port=$1 pids pid found=0
	pids=$(pgrep -af "uvicorn personal_world.worlds.production:app_from_env" || true)
	if [[ -z "$pids" ]]; then
		warn "no worlds server process found (already gone?)"
		SERVER_RUNNING=0; return 0
	fi
	for pid in $(printf '%s\n' "$pids" | awk -v want="--port $port" 'index($0, want){print $1}'); do
		local cmd
		cmd=$(tr '\0' ' ' <"/proc/$pid/cmdline" 2>/dev/null || true)
		if [[ "$cmd" == *"personal_world.worlds.production:app_from_env"* && "$cmd" == *"--port $port"* ]]; then
			kill "$pid"
			found=1
		else
			warn "pid $pid cmdline did not match the drill's server; leaving it alone"
		fi
	done
	[[ $found -eq 1 ]] || fail "drill's uvicorn on port $port not found via pgrep"
	local i=0
	while port_busy "$port"; do
		i=$((i + 1)); [[ $i -gt 100 ]] && fail "port $port still busy 10s after kill"
		sleep 0.1
	done
	SERVER_RUNNING=0
}

wait_health() {
	local i=0 code
	while :; do
		code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/healthz" 2>/dev/null || true)
		[[ "$code" = "200" ]] && return 0
		i=$((i + 1)); [[ $i -gt 200 ]] && { tail -20 "$WORK/server-$PORT.log" >&2 || true; fail "server not healthy after ~50s (see log above)"; }
		sleep 0.25
	done
}

# ── HTTP helper ───────────────────────────────────────────────────────
# The session id and CSRF token go into a 0600 curl config file, never
# argv. The server sets Secure cookies, so curl will not auto-resend them
# over http: the Cookie and X-CSRF-Token headers are sent explicitly.
api() { # METHOD PATH BODYFILE|"- OUTFILE  → prints http_code
	local method=$1 path=$2 bodyfile=$3 outfile=$4
	local cfg=$WORK/curl.cfg
	umask 077
	{
		printf 'url = "%s%s"\n' "$BASE" "$path"
		printf 'request = "%s"\n' "$method"
		printf 'header = "Origin: %s"\n' "$ORIGIN"
		if [[ -n "${SID:-}" ]]; then
			printf 'header = "Cookie: pw_session=%s; pw_csrf=%s"\n' "$SID" "$CSRF"
			printf 'header = "X-CSRF-Token: %s"\n' "$CSRF"
		fi
		printf 'header = "Content-Type: application/json"\n'
		[[ $bodyfile != "-" ]] && printf 'data = "@%s"\n' "$bodyfile"
		printf 'output = "%s"\n' "$outfile"
		printf 'silent\nshow-error\nwrite-out = "%%{http_code}"\n'
	} >"$cfg"
	curl --config "$cfg"
}

# Bootstrap sign-in: Origin is required even before a session exists, and
# the response's Set-Cookie lines carry the session + CSRF pair.
signin() {
	local body=$WORK/body/bootstrap.json hdr=$WORK/bootstrap.headers cfg=$WORK/curl-bootstrap.cfg
	umask 077
	printf '{"token": "%s"}' "$BOOTSTRAP_TOKEN" >"$body"
	{
		printf 'url = "%s/api/auth/bootstrap"\n' "$BASE"
		printf 'request = "POST"\n'
		printf 'header = "Origin: %s"\n' "$ORIGIN"
		printf 'header = "Content-Type: application/json"\n'
		printf 'data = "@%s"\n' "$body"
		printf 'output = "%s"\n' "$WORK/out/bootstrap.json"
		printf 'dump-header = "%s"\n' "$hdr"
		printf 'silent\nshow-error\nwrite-out = "%%{http_code}"\n'
	} >"$cfg"
	local code
	code=$(curl --config "$cfg")
	[[ "$code" = "200" ]] || { tail -20 "$WORK/server-$PORT.log" >&2 || true; fail "bootstrap sign-in -> $code"; }
	SID=$(awk 'BEGIN{IGNORECASE=1} /^set-cookie: pw_session=/{v=$0; sub(/^[^=]*=/,"",v); sub(/;.*/,"",v)} END{print v}' "$hdr")
	CSRF=$(awk 'BEGIN{IGNORECASE=1} /^set-cookie: pw_csrf=/{v=$0; sub(/^[^=]*=/,"",v); sub(/;.*/,"",v)} END{print v}' "$hdr")
	[[ -n "$SID" && -n "$CSRF" ]] || fail "bootstrap sign-in did not set the session cookies"
	rm -f "$body" "$hdr"
}

# Seed body files (plain JSON, no secrets).
put_json() { # NAME  json-content
	local f="$WORK/body/$1.json"
	printf '%s' "$2" >"$f"
	printf '%s' "$f"
}

# ── phase 1: seed instance A ──────────────────────────────────────────
seed_instance() {
	phase_begin "config-A"
	write_owner_config "$A_CFG"
	phase_end

	phase_begin "server-A-boot"
	start_server "$A_DATA" "$A_CFG"
	phase_end

	phase_begin "sign-in-A"
	signin
	phase_end

	phase_begin "api-seed"
	local code f
	# Two Kept, one Later, one Record — every memory table.
	f=$(put_json kept-1 '{"title":"drill kept alpha","body":"kettle verified","tags":["drill"]}')
	code=$(api POST /api/memory/kept "$f" "$WORK/out/seed-kept-1.json"); [[ "$code" = "200" ]] || fail "memory/kept 1 -> $code"
	f=$(put_json kept-2 '{"title":"drill kept beta","body":"orbit quiet"}')
	code=$(api POST /api/memory/kept "$f" "$WORK/out/seed-kept-2.json"); [[ "$code" = "200" ]] || fail "memory/kept 2 -> $code"
	f=$(put_json later-1 '{"title":"drill later alpha","body":"supplies"}')
	code=$(api POST /api/memory/later "$f" "$WORK/out/seed-later-1.json"); [[ "$code" = "200" ]] || fail "memory/later -> $code"
	f=$(put_json records-1 '{"title":"drill record alpha","body":"synthetic record","kind":"note"}')
	code=$(api POST /api/memory/records "$f" "$WORK/out/seed-records-1.json"); [[ "$code" = "200" ]] || fail "memory/records -> $code"
	phase_end

	phase_begin "snapshot-A"
	code=$(api GET "/api/memory/kept?limit=500" - "$WORK/out/a-kept.json"); [[ "$code" = "200" ]] || fail "A kept GET -> $code"
	code=$(api GET "/api/memory/later?limit=500" - "$WORK/out/a-later.json"); [[ "$code" = "200" ]] || fail "A later GET -> $code"
	code=$(api GET "/api/memory/records?limit=500" - "$WORK/out/a-records.json"); [[ "$code" = "200" ]] || fail "A records GET -> $code"
	code=$(api GET "/api/memory/history?limit=500" - "$WORK/out/a-history.json"); [[ "$code" = "200" ]] || fail "A history GET -> $code"
	A_HISTORY_COUNT=$("$VENV_PY" -c 'import json,sys;print(len(json.load(open(sys.argv[1]))))' "$WORK/out/a-history.json")
	phase_end
}

# ── phase 2: backup through the real route ────────────────────────────
run_backup() {
	phase_begin "backup-route"
	local code
	code=$(api POST /api/memory/backup - "$WORK/out/backup.json")
	[[ "$code" = "200" ]] || fail "memory/backup -> $code"
	local name
	name=$("$VENV_PY" -c 'import json,sys;print(json.load(open(sys.argv[1]))["file"])' "$WORK/out/backup.json")
	ARCHIVE="$BACKUPS_DIR/$name"
	[[ -f "$ARCHIVE" ]] || fail "backup route reported $name but no such file exists"
	[[ "$(stat -c %a "$BACKUPS_DIR")" = "700" ]] || fail "backups dir is not 0700"
	[[ "$(stat -c %a "$ARCHIVE")" = "600" ]] || fail "backup file is not 0600"
	phase_end

	phase_begin "server-A-stop"
	stop_server "$PORT"
	phase_end
}

# ── phase 3: refusals — fail closed, never overwrite ─────────────────
run_refusals() {
	phase_begin "refusals"
	"$VENV_PY" - "$ARCHIVE" "$A_DATA" "$BAD" <<'PY'
import json, shutil, sqlite3, sys
from pathlib import Path

from personal_world.worlds.memory_store import MemoryError_, restore_backup

archive, a_data, bad = (Path(a) for a in sys.argv[1:4])


def refused(path, target, what):
    try:
        restore_backup(path, target)
    except MemoryError_ as exc:
        return str(exc)
    raise SystemExit(f"{what} was NOT refused")


# 1. a corrupted copy: SQLite integrity (or readability) must fail closed.
corrupt = bad / "corrupt.db"
shutil.copyfile(archive, corrupt)
with open(corrupt, "r+b") as fh:
    fh.seek(0, 2)
    fh.seek(fh.tell() // 2)
    fh.write(b"\x00" * 512)
target = bad / "corrupt-target"
print(f"    corrupt backup refused: {refused(corrupt, target, 'a corrupt backup')}")
assert not target.exists(), "a refused corrupt restore created its target"

# 2. a valid SQLite file that is not a Worlds memory database.
not_worlds = bad / "not-worlds.db"
conn = sqlite3.connect(not_worlds)
conn.execute("CREATE TABLE unrelated (x)")
conn.commit()
conn.close()
target = bad / "nonworld-target"
print(f"    non-Worlds file refused: {refused(not_worlds, target, 'a non-Worlds file')}")
assert not target.exists(), "a refused non-Worlds restore created its target"

# 3. a target that already holds memory: the good archive must be refused
#    and A's rows must be untouched.
db = f"{a_data / 'worlds.db'}"
def counts():
    c = sqlite3.connect(db)
    try:
        return {t: c.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
                for t in ("kept", "later", "records")}
    finally:
        c.close()

before = counts()
print(f"    non-empty target refused: {refused(archive, a_data, 'a non-empty target')}")
after = counts()
assert before == after, f"a refused restore changed A: {before} -> {after}"
print(f"    A unchanged by the refused restore: {json.dumps(after, sort_keys=True)}")
PY
	phase_end
}

# ── phase 4: restore into a fresh dir B ───────────────────────────────
run_restore() {
	phase_begin "restore-function"
	"$VENV_PY" - "$ARCHIVE" "$B_DATA" "$WORK/out/restore.json" <<'PY'
import json, sys
from pathlib import Path

from personal_world.worlds.memory_store import restore_backup

counts = restore_backup(Path(sys.argv[1]), Path(sys.argv[2]))
Path(sys.argv[3]).write_text(json.dumps(counts, indent=2, sort_keys=True) + "\n")
print(f"    restored {json.dumps(counts, sort_keys=True)}")
PY
	[[ -f "$B_DATA/worlds.db" ]] || fail "restore produced no worlds.db in B"
	[[ "$(stat -c %a "$B_DATA/worlds.db")" = "600" ]] || fail "restored worlds.db is not 0600"
	phase_end
}

# ── phase 5: verify a working instance on B ───────────────────────────
verify_instance() {
	phase_begin "config-B"
	write_owner_config "$B_CFG"
	phase_end

	phase_begin "server-B-boot"
	start_server "$B_DATA" "$B_CFG"
	phase_end

	phase_begin "sign-in-B"
	signin
	phase_end

	phase_begin "api-verify"
	local code
	code=$(api GET "/api/memory/kept?limit=500" - "$WORK/out/b-kept.json"); [[ "$code" = "200" ]] || fail "B kept GET -> $code"
	code=$(api GET "/api/memory/later?limit=500" - "$WORK/out/b-later.json"); [[ "$code" = "200" ]] || fail "B later GET -> $code"
	code=$(api GET "/api/memory/records?limit=500" - "$WORK/out/b-records.json"); [[ "$code" = "200" ]] || fail "B records GET -> $code"
	code=$(api GET "/api/memory/history?limit=500" - "$WORK/out/b-history.json"); [[ "$code" = "200" ]] || fail "B history GET -> $code"
	"$VENV_PY" - "$WORK/out" "$A_HISTORY_COUNT" <<'PY'
import json, sys
from pathlib import Path

out, a_hist = Path(sys.argv[1]), int(sys.argv[2])


def load(name):
    return json.loads((out / name).read_text())


for table in ("kept", "later", "records"):
    a, b = load(f"a-{table}.json"), load(f"b-{table}.json")
    if sorted((r["id"], r["title"]) for r in a) != sorted((r["id"], r["title"]) for r in b):
        raise SystemExit(f"{table} rows differ after restore")
    if not b:
        raise SystemExit(f"{table} came back empty")
    print(f"    {table:8s} {len(b)} row(s) identical (id + title)")

b_hist = load("b-history.json")
if len(b_hist) != a_hist + 1:
    raise SystemExit(f"history count B={len(b_hist)} expected A({a_hist}) + 1 restored")
if not b_hist or b_hist[0]["event"] != "restored":
    raise SystemExit(f"newest history event is not 'restored': {b_hist[:1]}")
print(f"    history  {len(b_hist)} event(s) = A's {a_hist} + 1 restored")
PY
	phase_end

	phase_begin "server-B-stop"
	stop_server "$PORT"
	phase_end
}

# ── failure-path drill: a corrupted backup must be refused ────────────
corrupt_backup_drill() {
	phase_begin "corrupt-archive"
	"$VENV_PY" - "$ARCHIVE" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
with open(path, "r+b") as fh:
    fh.seek(0, 2)
    fh.seek(fh.tell() // 2)
    fh.write(b"\x00" * 512)
print(f"    corrupted {path.name} in place")
PY
	phase_end

	phase_begin "refuse-corrupt"
	local msg
	msg=$("$VENV_PY" - "$ARCHIVE" "$B_DATA" <<'PY'
import sys
from pathlib import Path

from personal_world.worlds.memory_store import MemoryError_, restore_backup

try:
    restore_backup(Path(sys.argv[1]), Path(sys.argv[2]))
except MemoryError_ as exc:
    print(exc)
else:
    raise SystemExit("a corrupted backup was NOT refused")
PY
	)
	[[ -n "$msg" ]] || fail "no refusal message after corrupting the backup"
	[[ ! -f "$B_DATA/worlds.db" ]] || fail "a refused corrupt restore wrote a worlds.db"
	say "    corrupt backup refused: $msg"
	phase_end
}

# ── main ──────────────────────────────────────────────────────────────
preflight
PORT=$(pick_port)
BASE=http://127.0.0.1:$PORT
ORIGIN=$BASE
SERVER_RUNNING=0
setup_work
trap cleanup EXIT

say "Project Worlds restore drill (rebuild/front-door)"
say "repo:    $REPO_ROOT"
say "server:  127.0.0.1:$PORT (bootstrap secret never printed)"
say "app:     personal_world.worlds.production:app_from_env"
say "workspace: $WORK"
[[ "$PORT" != "$PREFERRED_PORT" ]] && say "note: $PREFERRED_PORT busy; using $PORT"

seed_instance
run_backup

if [[ $CORRUPT_BACKUP -eq 1 ]]; then
	corrupt_backup_drill
	TOTAL=$(( $(now_ms) - DRILL_T0 ))
	head_phase "FAILURE-PATH REPORT (measured)"
	printf '    %-22s %7s\n' phase duration_ms
	while IFS=$'\t' read -r name ms; do printf '    %-22s %9s\n' "$name" "$ms"; done <"$TIMINGS_FILE"
	printf '    %-22s %9s\n' "─── total" "$TOTAL"
	say ""
	say "RESULT: PASS — a corrupted backup was refused and wrote nothing; $TOTAL ms wall-clock."
	exit 0
fi

run_refusals
run_restore
verify_instance

TOTAL=$(( $(now_ms) - DRILL_T0 ))
ARCHIVE_BYTES=$(stat -c %s "$ARCHIVE")
N_KEPT_A=$("$VENV_PY" -c 'import json,sys;print(len(json.load(open(sys.argv[1]))))' "$WORK/out/a-kept.json")
N_LATER_A=$("$VENV_PY" -c 'import json,sys;print(len(json.load(open(sys.argv[1]))))' "$WORK/out/a-later.json")
N_RECORDS_A=$("$VENV_PY" -c 'import json,sys;print(len(json.load(open(sys.argv[1]))))' "$WORK/out/a-records.json")

if [[ -n "$REPORT_DIR" ]]; then
	mkdir -p "$REPORT_DIR"
	cp "$WORK/timings.tsv" "$WORK/out/backup.json" "$WORK/out/restore.json" \
		"$WORK/out/a-kept.json" "$WORK/out/a-later.json" "$WORK/out/a-records.json" \
		"$WORK/out/a-history.json" "$WORK/out/b-kept.json" "$WORK/out/b-later.json" \
		"$WORK/out/b-records.json" "$WORK/out/b-history.json" "$REPORT_DIR/" 2>/dev/null || true
	say "evidence copied to: $REPORT_DIR"
fi

head_phase "DRILL REPORT (measured)"
printf '    %-22s %7s\n' phase duration_ms
while IFS=$'\t' read -r name ms; do printf '    %-22s %9s\n' "$name" "$ms"; done <"$TIMINGS_FILE"
printf '    %-22s %9s\n' "─── total" "$TOTAL"
say ""
say "backup:             $(basename "$ARCHIVE") (${ARCHIVE_BYTES} bytes, mode 0600)"
say "rows seeded on A:   kept=${N_KEPT_A} later=${N_LATER_A} records=${N_RECORDS_A} history=${A_HISTORY_COUNT}"
say "rows seen on B:     identical ids/titles via the API; history = A + 1 'restored' event"
say "refusals:           corrupt backup, non-Worlds file and non-empty target all refused; nothing written"
say ""
say "RESULT: PASS — Memory rows from A came back through the API on a fresh instance B; $TOTAL ms wall-clock."
